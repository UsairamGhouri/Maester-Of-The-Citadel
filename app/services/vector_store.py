"""
Vector Store Service
Manages persistent ChromaDB collections for book-isolated semantic search.
"""
import logging
import chromadb
from flask import current_app
from rank_bm25 import BM25Okapi

logger = logging.getLogger('CourseHelper.vector_store')

def _get_client() -> chromadb.PersistentClient:
    """Get or create the ChromaDB persistent client."""
    persist_dir = current_app.config['CHROMA_PERSIST_DIR']
    # Using the new PersistentClient API
    return chromadb.PersistentClient(path=persist_dir)


def create_collection(book_id: int) -> chromadb.Collection:
    """Create or get a ChromaDB collection specific to a book_id."""
    client = _get_client()
    collection_name = f"book_{book_id}"
    
    # We use get_or_create to ensure idempotency
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"book_id": book_id}
    )
    return collection


def add_documents(book_id: int, chunks: list[dict], embedding_model: str = 'nomic-embed-text', progress_callback=None):
    """
    Embed and insert text chunks into the book's vector collection.
    
    Args:
        book_id: ID of the book.
        chunks: List of dictionaries from pdf_processor containing 'text' and metadata.
        embedding_model: Model name for embeddings.
        progress_callback: Optional callback for embedding progress.
    """
    if not chunks:
        return

    from app.services.embeddings import embed_texts

    collection = create_collection(book_id)
    
    # Extract raw text for embedding
    texts = [chunk['text'] for chunk in chunks]
    
    logger.info(f"Generating embeddings for {len(texts)} text chunks (book_id={book_id})...")
    embeddings = embed_texts(texts, model_name=embedding_model, progress_callback=progress_callback)
    
    if not embeddings or len(embeddings) != len(texts):
        logger.error("Embedding generation failed or returned mismatched counts.")
        raise ValueError("Failed to generate embeddings for all chunks. Please check API limits or service status.")

    ids = []
    metadatas = []
    
    for i, chunk in enumerate(chunks):
        ids.append(f"text_chunk_{chunk['chunk_index']}")
        metadatas.append({
            "type": "text",
            "chunk_index": chunk['chunk_index'],
            "pages": ",".join(map(str, chunk['pages'])) # Chroma metadata values must be str, int, float or bool
        })
        
    logger.info(f"Upserting {len(ids)} text documents to collection book_{book_id}...")
    
    # Batch upserts to avoid memory spikes in ChromaDB
    UPSERT_BATCH = 500
    for batch_start in range(0, len(ids), UPSERT_BATCH):
        batch_end = min(batch_start + UPSERT_BATCH, len(ids))
        collection.upsert(
            ids=ids[batch_start:batch_end],
            documents=texts[batch_start:batch_end],
            embeddings=embeddings[batch_start:batch_end],
            metadatas=metadatas[batch_start:batch_end],
        )





def delete_collection(book_id: int):
    """Delete a book's ChromaDB collection."""
    if book_id in _bm25_cache:
        del _bm25_cache[book_id]
        
    client = _get_client()
    collection_name = f"book_{book_id}"
    try:
        client.delete_collection(name=collection_name)
        logger.info(f"Deleted ChromaDB collection: {collection_name}")
    except ValueError as e:
        # ChromaDB raises ValueError if the collection doesn't exist
        logger.warning(f"Could not delete collection {collection_name}: {e}")
    except Exception as e:
        logger.error(f"Error deleting collection {collection_name}: {e}")


# --- BM25 Cache ---
_bm25_cache = {}

def get_bm25_index(book_id: int):
    """
    Get or create a BM25 index for the book's documents.
    Returns: (bm25_instance, documents, metadatas)
    """
    if book_id in _bm25_cache:
        return _bm25_cache[book_id]

    collection = create_collection(book_id)
    # Get all documents from ChromaDB
    res = collection.get()
    
    if not res or not res.get("documents"):
        return None, [], [], []
        
    documents = res["documents"]
    metadatas = res["metadatas"]
    ids = res["ids"]
    
    # Tokenize for BM25 (simple whitespace tokenization)
    tokenized_corpus = [doc.lower().split() for doc in documents]
    
    bm25 = BM25Okapi(tokenized_corpus)
    
    _bm25_cache[book_id] = (bm25, documents, metadatas, ids)
    return _bm25_cache[book_id]
