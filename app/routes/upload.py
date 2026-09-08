"""
Upload Route — Handles PDF file uploads and triggers the processing pipeline.
"""
import os
import logging
from flask import Blueprint, request, jsonify, current_app

from app import db
from app.models.database import Book
from app.services.pdf_processor import extract_and_chunk
from app.services.vector_store import add_documents
import threading

logger = logging.getLogger('CourseHelper.upload')

upload_bp = Blueprint('upload', __name__)

ALLOWED_EXTENSIONS = {'.pdf', '.epub', '.docx', '.pptx'}


def _allowed_file(filename: str) -> bool:
    """Check if the file has an allowed extension."""
    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_EXTENSIONS


@upload_bp.route('/api/upload', methods=['POST'])
def upload_pdf():
    """Upload a PDF book and process it.
    
    Expects: multipart/form-data with a 'file' field.
    Optional: 'title' field to override the extracted/filename title.
    
    Returns:
        201: Book created with metadata and processing results.
        400: Missing file or invalid format.
        500: Processing error.
    """
    # ── Validate Request ───────────────────────────────────────────────
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided. Send a PDF in the "file" field.'}), 400

    file = request.files['file']

    if file.filename == '' or file.filename is None:
        return jsonify({'error': 'No file selected.'}), 400

    if not _allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Accepted formats: PDF, EPUB, DOCX, PPTX.'}), 400

    # ── Save the File ──────────────────────────────────────────────────
    upload_dir = current_app.config['UPLOAD_DIR']
    original_filename = file.filename

    # Create a temporary book record to get an ID
    book = Book(
        title=original_filename,  # Placeholder, will update after extraction
        filename=original_filename,
        file_path='',  # Will update after save
        processing_status='processing',
    )
    db.session.add(book)
    db.session.flush()  # Get the auto-generated ID without committing

    # Save with book_id prefix for uniqueness
    safe_filename = f'{book.id}_{original_filename}'
    file_path = os.path.join(upload_dir, safe_filename)
    file.save(file_path)

    book.file_path = file_path
    logger.info(f'Saved PDF: {file_path} (book_id={book.id})')

    db.session.commit()

    # ── Start Background Processing ────────────────────────────────────
    app = current_app._get_current_object()
    user_title = request.form.get('title', '').strip()
    
    thread = threading.Thread(
        target=process_book_background,
        args=(app, book.id, file_path, original_filename, user_title)
    )
    thread.start()

    return jsonify({
        'message': 'PDF uploaded. Processing started in background.',
        'book': book.to_dict(),
    }), 202

@upload_bp.route('/api/books/<int:book_id>/status', methods=['GET'])
def get_book_status(book_id: int):
    book = Book.query.get(book_id)
    if not book:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'book': book.to_dict()})

def process_book_background(app, book_id, file_path, original_filename, user_title):
    with app.app_context():
        book = Book.query.get(book_id)
        if not book:
            return

        try:
            config = app.config
            result = extract_and_chunk(
                file_path=file_path,
                chunk_size=config.get('CHUNK_SIZE', 1000),
                overlap=config.get('CHUNK_OVERLAP', 200),
            )

            metadata = result['metadata']
            chunks = result['chunks']

            book.title = (
                user_title
                or metadata.get('title')
                or os.path.splitext(original_filename)[0]
            )
            book.total_pages = metadata.get('total_pages', 0)
            book.processed_pages = book.total_pages # Extracted text
            book.total_chunks = len(chunks)
            book.processing_status = 'text_extracted'
            db.session.commit()

            book.processing_status = 'indexing'
            db.session.commit()

            # ── Vector Indexing (ChromaDB) ────────────────────────────────────
            embedding_model = config.get('EMBEDDING_MODEL', 'nomic-embed-text')
            
            import time
            _last_commit_time = [time.monotonic()]
            
            def on_progress(processed, total):
                book.processed_chunks = processed
                now = time.monotonic()
                # Only commit to DB every 5 seconds to avoid I/O thrashing
                if now - _last_commit_time[0] >= 5 or processed >= total:
                    db.session.commit()
                    _last_commit_time[0] = now
            
            add_documents(book.id, chunks, embedding_model=embedding_model, progress_callback=on_progress)
            
            book.processing_status = 'completed'
            db.session.commit()

            logger.info(
                f'Book processed and indexed: "{book.title}" — '
                f'{book.total_pages} pages, {book.total_chunks} chunks'
            )

        except Exception as e:
            book.processing_status = 'failed'
            db.session.commit()
            logger.error(f'PDF processing failed for book_id={book.id}: {e}', exc_info=True)
