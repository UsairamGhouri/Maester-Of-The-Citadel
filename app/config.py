import os
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'), override=True)


class Config:
    """Application configuration loaded from environment variables."""

    # ── Flask ──────────────────────────────────────────────────────────
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', '1') == '1'

    # ── Database ───────────────────────────────────────────────────────
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    DB_PATH = os.path.join(DATA_DIR, 'course_helper.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── File Paths ─────────────────────────────────────────────────────
    STATIC_DIR = os.path.join(BASE_DIR, 'app', 'static')
    UPLOAD_DIR = os.path.join(STATIC_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200 MB max upload

    # ── ChromaDB ───────────────────────────────────────────────────────
    CHROMA_PERSIST_DIR = os.path.join(BASE_DIR, 'chroma_data')

        

    # ── Ollama (Local Models) ──────────────────────────────────────────
    OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'all-minilm')
    FALLBACK_LLM_MODEL = os.getenv('FALLBACK_LLM_MODEL', 'qwen2.5:1.5b')

    # ── RAG Parameters ─────────────────────────────────────────────────
    CHUNK_SIZE = 1000       # characters per text chunk
    CHUNK_OVERLAP = 100     # character overlap between chunks
    TOP_K_RESULTS = 3       # number of retrieval results per query
