"""
LLM Service
Handles interaction with local Ollama models for RAG answer generation.
"""
import logging
from flask import current_app

logger = logging.getLogger('CourseHelper.llm')

SYSTEM_PROMPT = (
    "You are a strict AI. You MUST answer the question using ONLY the provided Context.\n"
    "If the Context does not contain the answer, you MUST output exactly: 'The Citadel archives do not contain the answer to this question.'\n"
    "Do not provide any outside knowledge."
)


def generate_answer(query: str, context: str, chat_history: list = None):
    """
    Generate an answer using local Ollama given the user query and the retrieved context.
    
    Uses proper system/user/assistant message roles for better model comprehension,
    and streams the response token-by-token.
    
    Args:
        query: The user's question.
        context: The assembled text chunks retrieved from ChromaDB.
        chat_history: List of previous messages [{"role": "user"/"assistant", "content": "..."}].
        
    Yields:
        Chunks of the generated answer string (streamed).
    """
    model_name = current_app.config.get('FALLBACK_LLM_MODEL', 'llama3.2')

    # Build the message list with proper roles
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
    ]

    # Inject chat history as proper role-tagged messages
    if chat_history:
        for msg in chat_history:
            messages.append({
                'role': msg['role'],  # 'user' or 'assistant'
                'content': msg['content'],
            })

    # The current user turn: context + question
    user_message = f"Based STRICTLY on the context below, answer the question. Do NOT use outside knowledge. If the context does not contain the answer, reply EXACTLY with: 'The Citadel archives do not contain the answer to this question.'\n\nContext from the tome:\n{context}\n\nQuestion: {query}"
    messages.append({'role': 'user', 'content': user_message})

    try:
        import ollama
        logger.info(f"Generating answer with Ollama ({model_name})")

        response = ollama.chat(
            model=model_name,
            messages=messages,
            stream=True,
            options={
                'temperature': 0.1,
                'repeat_penalty': 1.05,
                'num_ctx': 4096,
            }
        )
        for chunk in response:
            if chunk and 'message' in chunk and chunk['message'].get('content'):
                yield chunk['message']['content']

    except Exception as e:
        logger.error(f"Error generating answer with Ollama: {e}")
        yield f"I encountered an error while trying to generate the answer. Please ensure Ollama is running and '{model_name}' is installed."
