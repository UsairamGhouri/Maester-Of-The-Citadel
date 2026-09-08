"""
SQLAlchemy models for the Course Helper application.

Tables:
    - Book: Uploaded PDF metadata and library management.
    - ImageAsset: Extracted images with generated captions.
    - ChatMessage: Persistent chat history per book session.
"""
from datetime import datetime, timezone

from app import db


class Book(db.Model):
    """Represents an uploaded PDF book in the user's library."""
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(500), nullable=False)
    filename = db.Column(db.String(500), nullable=False)
    file_path = db.Column(db.String(1000), nullable=False)
    total_pages = db.Column(db.Integer, default=0)
    processed_pages = db.Column(db.Integer, default=0)
    total_images = db.Column(db.Integer, default=0)
    total_chunks = db.Column(db.Integer, default=0)
    processed_chunks = db.Column(db.Integer, default=0)
    upload_timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    processing_status = db.Column(
        db.String(50), default='pending'
    )  # pending | processing | completed | failed

    # Relationships (cascade delete all children)
    images = db.relationship(
        'ImageAsset', backref='book', lazy=True,
        cascade='all, delete-orphan'
    )
    messages = db.relationship(
        'ChatMessage', backref='book', lazy=True,
        cascade='all, delete-orphan'
    )

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'filename': self.filename,
            'total_pages': self.total_pages,
            'processed_pages': self.processed_pages,
            'total_images': self.total_images,
            'total_chunks': self.total_chunks,
            'processed_chunks': self.processed_chunks,
            'upload_timestamp': self.upload_timestamp.isoformat() if self.upload_timestamp else None,
            'processing_status': self.processing_status,
        }


class ImageAsset(db.Model):
    """An image extracted from a PDF with its AI-generated caption."""
    __tablename__ = 'image_assets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    book_id = db.Column(
        db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False
    )
    page_number = db.Column(db.Integer, nullable=False)
    image_index = db.Column(db.Integer, nullable=False)
    file_path = db.Column(db.String(1000), nullable=False)
    caption = db.Column(db.Text, default='')
    width = db.Column(db.Integer, default=0)
    height = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'book_id': self.book_id,
            'page_number': self.page_number,
            'image_index': self.image_index,
            'file_path': self.file_path,
            'caption': self.caption,
            'width': self.width,
            'height': self.height,
        }


class ChatMessage(db.Model):
    """A single chat message (user or assistant) tied to a book session."""
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    book_id = db.Column(
        db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False
    )
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    model_used = db.Column(db.String(50), default='')  # which LLM answered
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        return {
            'id': self.id,
            'book_id': self.book_id,
            'role': self.role,
            'content': self.content,
            'model_used': self.model_used,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }
