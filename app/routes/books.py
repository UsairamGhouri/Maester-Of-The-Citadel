"""
Books Route — CRUD endpoints for managing the book library.
"""
import os
import shutil
import logging
from flask import Blueprint, jsonify, current_app, send_file

from app import db
from app.models.database import Book
from app.services.vector_store import delete_collection

logger = logging.getLogger('CourseHelper.books')

books_bp = Blueprint('books', __name__)


@books_bp.route('/api/books', methods=['GET'])
def list_books():
    """Return all books in the library, ordered by upload date (newest first)."""
    books = Book.query.order_by(Book.upload_timestamp.desc()).all()
    return jsonify({
        'books': [book.to_dict() for book in books],
        'total': len(books),
    })


@books_bp.route('/api/books/<int:book_id>', methods=['GET'])
def get_book(book_id: int):
    """Return details for a single book, including image and message counts."""
    book = Book.query.get(book_id)
    if not book:
        return jsonify({'error': f'Book with id {book_id} not found.'}), 404

    data = book.to_dict()
    data['image_count'] = len(book.images)
    data['message_count'] = len(book.messages)

    return jsonify({'book': data})


@books_bp.route('/api/books/<int:book_id>/file', methods=['GET'])
def get_book_file(book_id: int):
    """Serve the original PDF file for a book."""
    book = Book.query.get(book_id)
    if not book:
        return jsonify({'error': f'Book with id {book_id} not found.'}), 404
        
    if not book.file_path or not os.path.exists(book.file_path):
        return jsonify({'error': 'PDF file not found on disk.'}), 404
        
    return send_file(book.file_path, mimetype='application/pdf')


@books_bp.route('/api/books/<int:book_id>', methods=['DELETE'])
def delete_book(book_id: int):
    """Delete a book and all associated resources (cascade deletion).
    
    Cleanup order:
        1. Delete the source PDF from disk
        2. Delete DB records (Book + cascaded ChatMessage)
        3. Drop ChromaDB collection
    """
    book = Book.query.get(book_id)
    if not book:
        return jsonify({'error': f'Book with id {book_id} not found.'}), 404

    title = book.title
    logger.info(f'Deleting book: "{title}" (id={book_id})')

    # ── 1. Delete the source PDF ───────────────────────────────────────
    if book.file_path and os.path.exists(book.file_path):
        os.remove(book.file_path)
        logger.info(f'Deleted PDF: {book.file_path}')

    # ── 2. Delete DB records (cascade handles children) ────────────────
    db.session.delete(book)
    db.session.commit()
    logger.info(f'Deleted book record and cascaded children for id={book_id}')

    # ── 3. ChromaDB collection cleanup ─────────────────────────────────
    delete_collection(book_id)

    return jsonify({
        'message': f'Book "{title}" and all associated data deleted successfully.',
        'deleted_book_id': book_id,
    })



