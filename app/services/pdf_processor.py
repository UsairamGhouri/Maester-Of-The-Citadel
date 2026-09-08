"""
PDF Processing Service
Handles text extraction and chunking from PDF files using PyMuPDF (fitz).
Image extraction will be added in Phase 3.
"""
import os
import logging
import pymupdf

logger = logging.getLogger('CourseHelper.pdf_processor')


def get_pdf_metadata(pdf_path: str) -> dict:
    """Extract basic metadata from a PDF file.
    
    Returns:
        dict with keys: title, total_pages, author
    """
    doc = pymupdf.open(pdf_path)
    metadata = doc.metadata or {}

    title = metadata.get('title', '').strip()
    author = metadata.get('author', '').strip()
    total_pages = len(doc)

    doc.close()

    return {
        'title': title if title else None,
        'author': author if author else None,
        'total_pages': total_pages,
    }


def extract_text_by_page(pdf_path: str) -> list[dict]:
    """Extract raw text from each page of a PDF.
    
    Returns:
        List of dicts: [{"page": 1, "text": "..."}, ...]
    """
    doc = pymupdf.open(pdf_path)
    pages = []
    total_pages = len(doc)

    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        text = page.get_text('text').strip()
        if text:
            pages.append({
                'page': page_num + 1,  # 1-indexed
                'text': text,
            })

    doc.close()
    logger.info(f'Extracted text from {len(pages)}/{total_pages} pages: {pdf_path}')
    return pages


def chunk_text(
    pages: list[dict],
    chunk_size: int = 1000,
    overlap: int = 200
) -> list[dict]:
    """Segment page texts into overlapping chunks for embedding.
    
    Strategy:
        - Concatenate all page text with page markers
        - Split into chunks of `chunk_size` characters with `overlap` character overlap
        - Track which page(s) each chunk comes from
    
    Args:
        pages: Output from extract_text_by_page()
        chunk_size: Target characters per chunk
        overlap: Character overlap between consecutive chunks
    
    Returns:
        List of dicts: [{"text": "...", "chunk_index": 0, "pages": [1, 2]}, ...]
    """
    if not pages:
        return []

    # Build a flat text with page boundary tracking
    # Each entry: (start_char_index, page_number)
    page_boundaries = []
    full_text_parts = []
    current_pos = 0

    for page_data in pages:
        page_boundaries.append((current_pos, page_data['page']))
        full_text_parts.append(page_data['text'])
        current_pos += len(page_data['text']) + 1  # +1 for the newline separator

    full_text = '\n'.join(full_text_parts)

    if not full_text.strip():
        return []

    # Generate overlapping chunks
    chunks = []
    start = 0
    chunk_index = 0

    while start < len(full_text):
        end = min(start + chunk_size, len(full_text))

        # Try to break at a sentence/paragraph boundary if possible
        chunk_text_raw = full_text[start:end]

        # If we're not at the very end, try to find a clean break point
        if end < len(full_text):
            # Look for the last paragraph break, sentence end, or space
            for delimiter in ['\n\n', '.\n', '. ', '\n', ' ']:
                last_break = chunk_text_raw.rfind(delimiter)
                if last_break > chunk_size * 0.5:  # Don't break too early
                    end = start + last_break + len(delimiter)
                    chunk_text_raw = full_text[start:end]
                    break

        chunk_text_clean = chunk_text_raw.strip()

        if chunk_text_clean:
            # Determine which pages this chunk spans
            chunk_pages = _get_pages_for_range(page_boundaries, start, end)

            chunks.append({
                'text': chunk_text_clean,
                'chunk_index': chunk_index,
                'pages': chunk_pages,
                'start_char': start,
                'end_char': end,
            })
            chunk_index += 1

        # Advance: use the actual chunk length minus overlap, but never less
        # than a minimum step to avoid infinite/excessive loops on short text
        actual_chunk_len = end - start
        step = max(actual_chunk_len - overlap, chunk_size - overlap, 1)
        start = start + step

    logger.info(
        f'Created {len(chunks)} chunks from {len(pages)} pages '
        f'(chunk_size={chunk_size}, overlap={overlap})'
    )
    return chunks


def _get_pages_for_range(
    page_boundaries: list[tuple[int, int]],
    start: int,
    end: int
) -> list[int]:
    """Determine which page numbers a character range [start, end) spans."""
    pages = []
    for i, (boundary_start, page_num) in enumerate(page_boundaries):
        # Determine the end of this page's text
        if i + 1 < len(page_boundaries):
            boundary_end = page_boundaries[i + 1][0]
        else:
            boundary_end = float('inf')

        # Check if this page overlaps with our chunk range
        if boundary_start < end and boundary_end > start:
            pages.append(page_num)

    return pages if pages else [1]


def extract_and_chunk(
    file_path: str,
    chunk_size: int = 1000,
    overlap: int = 200
) -> dict:
    """End-to-end pipeline: extract text from document and chunk it."""
    from app.services.document_processor import extract_text, get_document_metadata
    
    metadata = get_document_metadata(file_path)
    pages = extract_text(file_path)
    metadata['total_pages'] = len(pages) if metadata.get('total_pages', 0) == 0 else metadata['total_pages']

    chunks = chunk_text(pages, chunk_size, overlap)

    return {
        'metadata': metadata,
        'pages': pages,
        'chunks': chunks
    }



