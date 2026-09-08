"""
Chat Route
Handles user queries and interacts with the RAG service to generate answers.
"""
import logging
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app
import json
import re
import os

from app import db
from app.models.database import Book, ChatMessage
from app.services.rag import query_book, query_all_books

logger = logging.getLogger('CourseHelper.chat')

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/api/books/<int:book_id>/chat', methods=['POST'])
def chat(book_id: int):
    """
    Handle a chat message for a specific book.
    
    Expects JSON:
    {
        "message": "What is machine learning?"
    }
    
    Returns:
        JSON with the answer and retrieved context sources.
    """
    book = Book.query.get_or_404(book_id)
    
    # Check if book is fully processed
    if book.processing_status != 'completed':
        return jsonify({
            'error': f'Book is not fully processed yet (status: {book.processing_status}).'
        }), 400
        
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'Message is required.'}), 400
        
    user_message_text = data['message'].strip()
    if not user_message_text:
        return jsonify({'error': 'Message cannot be empty.'}), 400
        
        
        
    # 1. Fetch chat history for context (last 2 messages = 1 QA turn)
    recent_msgs = ChatMessage.query.filter_by(book_id=book.id).order_by(ChatMessage.timestamp.desc()).limit(2).all()
    recent_msgs.reverse()
    chat_history = [{"role": msg.role, "content": msg.content} for msg in recent_msgs]

    # 2. Save user message to database
    user_msg = ChatMessage(
        book_id=book.id,
        role='user',
        content=user_message_text
    )
    db.session.add(user_msg)
    db.session.commit()
    
    # 3. Query the RAG pipeline
    try:
        rag_result = query_book(book.id, user_message_text, chat_history=chat_history)
        answer_stream = rag_result['answer_stream']
        sources = rag_result['context_sources']
        
        def generate():
            try:
                # First yield the sources as a JSON payload
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
                
                full_answer = ""
                for chunk in answer_stream:
                    full_answer += chunk
                    # Yield each text chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
                    
                # After streaming is complete, save to DB
                ai_msg = ChatMessage(
                    book_id=book.id,
                    role='assistant',
                    content=full_answer
                )
                db.session.add(ai_msg)
                db.session.commit()
                
                yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id})}\n\n"
            except Exception as e:
                logger.error(f"Error during stream generation: {e}")
                yield f"data: {json.dumps({'type': 'chunk', 'text': f'<br><br>**[System Error: {str(e)}]**'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')
        
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        return jsonify({'error': 'Failed to process chat message.'}), 500

@chat_bp.route('/api/books/<int:book_id>/chat', methods=['GET'])
def get_chat_history(book_id: int):
    """Get the chat history for a specific book."""
    book = Book.query.get_or_404(book_id)
    
    messages = ChatMessage.query.filter_by(book_id=book.id).order_by(ChatMessage.timestamp.asc()).all()
    
    return jsonify({
        'book_id': book.id,
        'messages': [msg.to_dict() for msg in messages],
        'total': len(messages)
    }), 200

@chat_bp.route('/api/books/<int:book_id>/export', methods=['GET'])
def export_chat(book_id: int):
    """
    Export chat history as a Markdown file.
    """
    book = Book.query.get_or_404(book_id)
    messages = ChatMessage.query.filter_by(book_id=book.id).order_by(ChatMessage.timestamp).all()
    
    md_content = f"# Chat History: {book.title}\n\n"
    for msg in messages:
        role = "User" if msg.role == "user" else "AI"
        md_content += f"**{role}** ({msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')}):\n{msg.content}\n\n---\n\n"
        
    from flask import Response
    return Response(
        md_content,
        mimetype="text/markdown",
        headers={"Content-disposition": f"attachment; filename=chat_export_{book_id}.md"}
    )

@chat_bp.route('/api/books/global/chat', methods=['POST'])
def chat_global():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'Message is required.'}), 400
        
    user_message_text = data['message'].strip()
    if not user_message_text:
        return jsonify({'error': 'Message cannot be empty.'}), 400
        
        
        
    try:
        rag_result = query_all_books(user_message_text)
        answer_stream = rag_result['answer_stream']
        sources = rag_result['context_sources']
        
        def generate():
            try:
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
                
                full_answer = ""
                for chunk in answer_stream:
                    full_answer += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
                    
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            except Exception as e:
                logger.error(f"Error during global stream generation: {e}")
                yield f"data: {json.dumps({'type': 'chunk', 'text': f'<br><br>**[System Error: {str(e)}]**'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return Response(stream_with_context(generate()), mimetype='text/event-stream')
        
    except Exception as e:
        logger.error(f"Error processing global chat message: {e}")
        return jsonify({'error': 'Failed to process chat message.'}), 500

@chat_bp.route('/api/books/global/chat', methods=['GET'])
def get_global_chat_history():
    return jsonify({
        'book_id': 'global',
        'messages': [],
        'total': 0
    }), 200

@chat_bp.route('/api/books/<int:book_id>/chat', methods=['DELETE'])
def clear_chat(book_id: int):
    """Clear chat history for a specific book."""
    try:
        ChatMessage.query.filter_by(book_id=book_id).delete()
        db.session.commit()
        return jsonify({'message': 'Chat history cleared successfully.'}), 200
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to clear chat history.'}), 500
