"""
RAG Service
Handles the Retrieval-Augmented Generation pipeline.
"""
import logging
from app.services.vector_store import create_collection, get_bm25_index
from app.services.embeddings import embed_texts
from app.services.llm import generate_answer
import numpy as np

logger = logging.getLogger('CourseHelper.rag')




def expand_query(query: str) -> list[str]:
    """Uses the local LLM to generate synonymous queries for better retrieval."""
    try:
        # pyrefly: ignore [missing-import]
        import ollama
        from flask import current_app
        model_name = current_app.config.get('FALLBACK_LLM_MODEL', 'llama3.2')
        prompt = (
            "You are a helpful search assistant. Generate 3 synonymous search queries "
            "that mean the exact same thing as the original query but use different terminology. "
            "Return ONLY the 3 queries separated by newlines, with no bullet points, numbers, or intro text.\n\n"
            f"Original query: {query}"
        )
        response = ollama.chat(
            model=model_name,
            messages=[{'role': 'user', 'content': prompt}],
            stream=False,
            options={'temperature': 0.7}
        )
        content = response.get('message', {}).get('content', '')
        expanded = [line.strip().strip('-').strip('1234567890.').strip() for line in content.split('\n') if line.strip()]
        return [query] + expanded[:3]
    except Exception as e:
        logger.error(f"Error expanding query: {e}")
        return [query]


def compute_rrf(dense_results: list, sparse_results: list, k: int = 60) -> list:
    """
    Compute Reciprocal Rank Fusion on dense and sparse result lists.
    """
    rrf_scores = {}
    
    for rank, item in enumerate(dense_results):
        item_id = item['id']
        if item_id not in rrf_scores:
            rrf_scores[item_id] = {'item': item, 'score': 0.0}
        rrf_scores[item_id]['score'] += 1.0 / (k + rank + 1)
        
    for rank, item in enumerate(sparse_results):
        item_id = item['id']
        if item_id not in rrf_scores:
            rrf_scores[item_id] = {'item': item, 'score': 0.0}
        rrf_scores[item_id]['score'] += 1.0 / (k + rank + 1)
        
    fused_results = []
    for item_id, data in rrf_scores.items():
        fused_item = dict(data['item'])
        fused_item['rrf_score'] = data['score']
        fused_results.append(fused_item)
        
    fused_results.sort(key=lambda x: x['rrf_score'], reverse=True)
    return fused_results


def _hybrid_search_and_rerank(original_query: str, expanded_queries: list[str], query_vectors: list, books: list, top_k: int = 5) -> list:
    """
    Core engine combining BM25, ChromaDB, RRF, and Cross-Encoder reranking.
    """
    tokenized_query = " ".join(expanded_queries).lower().split()
    
    all_dense = []
    all_sparse = []
    
    # 1. Retrieve candidates from all books
    for book in books:
        # Dense Retrieval (ChromaDB)
        collection = create_collection(book.id)
        try:
            dense_res = collection.query(query_embeddings=query_vectors, n_results=10)
            if dense_res and dense_res.get('ids'):
                for q_idx in range(len(query_vectors)):
                    if len(dense_res['ids']) > q_idx and dense_res['ids'][q_idx]:
                        for i in range(len(dense_res['ids'][q_idx])):
                            all_dense.append({
                                'id': f"{book.id}_{dense_res['ids'][q_idx][i]}",
                                'doc': dense_res['documents'][q_idx][i],
                                'meta': dense_res['metadatas'][q_idx][i],
                                'book_id': book.id,
                                'book_title': book.title,
                                'distance': dense_res['distances'][q_idx][i] if 'distances' in dense_res and dense_res['distances'] else 0.0
                            })
        except Exception as e:
            logger.error(f"Error dense querying book {book.id}: {e}")

        # Sparse Retrieval (BM25)
        bm25, documents, metadatas, ids = get_bm25_index(book.id)
        if bm25:
            scores = bm25.get_scores(tokenized_query)
            top_indices = np.argsort(scores)[::-1][:20]
            for idx in top_indices:
                if scores[idx] > 0: # Only keep matches
                    all_sparse.append({
                        'id': f"{book.id}_{ids[idx]}",
                        'doc': documents[idx],
                        'meta': metadatas[idx],
                        'book_id': book.id,
                        'book_title': book.title,
                        'score': scores[idx]
                    })
                    
    # Deduplicate all_dense by id since multiple queries might retrieve the same chunk
    unique_dense = {}
    for item in all_dense:
        if item['id'] not in unique_dense or item['distance'] < unique_dense[item['id']]['distance']:
            unique_dense[item['id']] = item
    all_dense = list(unique_dense.values())
    
    # Globally sort candidates across all books BEFORE RRF
    # Dense: lower distance is better
    all_dense.sort(key=lambda x: x['distance'])
    # Sparse: higher score is better
    all_sparse.sort(key=lambda x: x['score'], reverse=True)
                    
    # 2. Reciprocal Rank Fusion
    fused_candidates = compute_rrf(all_dense, all_sparse)
    
    # Take top candidates based on fused scores
    sorted_results = fused_candidates
        
    top_results = sorted_results[:top_k]
    
    return top_results


def _build_context_and_stream(query: str, final_results: list, chat_history: list = None) -> dict:
    """Formats the results and yields the LLM stream."""
    context_pieces = []
    context_sources = []
    
    for item in final_results:
        doc = item['doc']
        meta = item['meta']
        title = item.get('book_title', 'Unknown Book')
        
        if meta.get('type') == 'image':
            page = meta.get('page', 'Unknown')
            context_pieces.append(f"[{title} - Image on Page {page}]: {doc}")
        else:
            pages = meta.get('pages', 'Unknown')
            context_pieces.append(f"[{title} - Text on pages {pages}]: {doc}")
            
        context_sources.append({
            "type": meta.get('type'),
            "content": doc,
            "metadata": meta
        })
        
    if not context_pieces:
        return {
            "answer_stream": (chunk for chunk in ["I couldn't find any relevant information to answer your question."]),
            "context_sources": []
        }
        
    context_str = "\n\n".join(context_pieces)
    answer_stream = generate_answer(query, context_str, chat_history=chat_history)
    
    return {
        "answer_stream": answer_stream,
        "context_sources": context_sources
    }


def query_book(book_id: int, query: str, top_k: int = 5, chat_history: list = None) -> dict:
    """Retrieve relevant context from a specific book and generate an answer."""
    logger.info(f"RAG query for book_id={book_id}: '{query}'")
    
    from app.models.database import Book
    book = Book.query.get(book_id)
    if not book:
        return {"answer_stream": (chunk for chunk in ["Book not found."]), "context_sources": []}
        
    search_query = query
    if chat_history and len(chat_history) > 0:
        prev_user_msgs = [m['content'] for m in chat_history if m['role'] == 'user']
        if len(prev_user_msgs) > 0:
            search_query = f"{prev_user_msgs[-1]} {query}"
            
    expanded_queries = expand_query(search_query)
    query_embeddings = embed_texts(expanded_queries)
    if not query_embeddings:
        return {"answer_stream": (chunk for chunk in ["Unable to process your query. The system could not generate embeddings (Check API rate limits or Ollama status)."]), "context_sources": []}
    
    final_results = _hybrid_search_and_rerank(query, expanded_queries, query_embeddings, [book], top_k=top_k)
    return _build_context_and_stream(query, final_results, chat_history=chat_history)


def query_all_books(query: str, top_k: int = 5, chat_history: list = None) -> dict:
    """Retrieve relevant context from all books and generate a unified answer."""
    logger.info(f"Global RAG query: '{query}'")
    
    search_query = query
    if chat_history and len(chat_history) > 0:
        prev_user_msgs = [m['content'] for m in chat_history if m['role'] == 'user']
        if len(prev_user_msgs) > 0:
            search_query = f"{prev_user_msgs[-1]} {query}"
            
    expanded_queries = expand_query(search_query)
    query_embeddings = embed_texts(expanded_queries)
    if not query_embeddings:
        return {"answer_stream": (chunk for chunk in ["Unable to process your query. The system could not generate embeddings (Check API rate limits or Ollama status)."]), "context_sources": []}
    
    from app.models.database import Book
    books = Book.query.filter_by(processing_status='completed').all()
    
    if not books:
        return {"answer_stream": (chunk for chunk in ["There are no books in the library yet."]), "context_sources": []}
        
    final_results = _hybrid_search_and_rerank(query, expanded_queries, query_embeddings, books, top_k=top_k)
    return _build_context_and_stream(query, final_results, chat_history=chat_history)
