"""
Embeddings Service
Generates vector embeddings using a local Ollama model (e.g., nomic-embed-text).
Uses large batches and concurrent requests to minimize latency.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from ollama import Client

logger = logging.getLogger('CourseHelper.embeddings')

BATCH_SIZE = 10    # Keep very small for CPU — so the progress bar updates continuously
MAX_WORKERS = 1    # Ollama can only run one model at a time; concurrency just queues


def _embed_batch(client: Client, model_name: str, batch_indices: list[int], batch_texts: list[str]) -> list[tuple[int, list[float]]]:
    """Embed a single batch and return (original_index, embedding) pairs."""
    response = client.embed(model=model_name, input=batch_texts)
    batch_embeddings = response.get('embeddings', [])
    results = []
    for i, emb in enumerate(batch_embeddings):
        if emb:
            results.append((batch_indices[i], emb))
    return results


def embed_texts(texts: list[str], model_name: str = None, progress_callback=None) -> list[list[float]]:
    """
    Generate embeddings for a list of text strings using Ollama's batch API.
    
    Uses concurrent workers to overlap HTTP latency when there are many batches.
    
    Args:
        texts: A list of text chunks.
        model_name: The embedding model to use.
        progress_callback: A function that takes (processed_count, total_count)
        
    Returns:
        List of embedding vectors (list of floats).
    """
    if not texts:
        return []

    from app.config import Config
    if model_name is None:
        model_name = Config.EMBEDDING_MODEL

    # Filter out empty texts but track their original indices
    valid_entries = []
    for idx, text in enumerate(texts):
        if text.strip():
            valid_entries.append((idx, text))

    if not valid_entries:
        return []

    total = len(texts)
    embeddings = [None] * total  # Pre-allocate to maintain order
    processed = 0

    # ── Offline Mode: Local Ollama Embeddings ──
    logger.info(f"Using Local Embeddings (Ollama: {model_name}) for {len(valid_entries)} chunks")
    try:
        from app.config import Config
        client = Client(host=Config.OLLAMA_HOST)

        # Build list of batches
        batches = []
        for batch_start in range(0, len(valid_entries), BATCH_SIZE):
            batch = valid_entries[batch_start:batch_start + BATCH_SIZE]
            batch_indices = [entry[0] for entry in batch]
            batch_texts = [entry[1] for entry in batch]
            batches.append((batch_indices, batch_texts))

        # Use concurrency only when there are enough batches to benefit
        num_workers = min(MAX_WORKERS, len(batches))

        if num_workers <= 1:
            # Sequential path — no thread overhead
            for batch_indices, batch_texts in batches:
                results = _embed_batch(client, model_name, batch_indices, batch_texts)
                for idx, emb in results:
                    embeddings[idx] = emb
                processed += len(batch_texts)
                if progress_callback:
                    progress_callback(min(processed, total), total)
        else:
            # Concurrent path — overlap HTTP round-trips
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                future_to_size = {}
                for batch_indices, batch_texts in batches:
                    future = executor.submit(_embed_batch, client, model_name, batch_indices, batch_texts)
                    future_to_size[future] = len(batch_texts)

                for future in as_completed(future_to_size):
                    results = future.result()
                    for idx, emb in results:
                        embeddings[idx] = emb
                    processed += future_to_size[future]
                    if progress_callback:
                        progress_callback(min(processed, total), total)

    except Exception as e:
        logger.error(f"Error generating local embeddings: {e}")

    # Filter out None entries (from empty texts that were skipped)
    return [emb for emb in embeddings if emb is not None]
