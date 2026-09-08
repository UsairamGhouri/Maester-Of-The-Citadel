# Maester Of The Citadel - AI Course Helper

Maester Of The Citadel is a highly-optimized, fully-offline, Game of Thrones-themed AI course assistant. It allows you to upload documents (PDF, EPUB, DOCX, PPTX) into your personal library and seek wisdom from the texts using local AI models.

## Core Features
*   **100% Offline Architecture:** Relies exclusively on local models via Ollama and SentenceTransformers for true privacy and offline capabilities. No cloud API keys required!
*   **Themed UI & Chat History:** Features a rich Game of Thrones / Maester visual aesthetic with glassmorphism, dynamic scrolling, and thematic responses. You can even export your chats to markdown chronciles!
*   **The Maester's Rulebook:** Contains an interactive, scroll-themed rulebook modal featuring a procedural CSS parchment texture that teaches users how to write optimal queries.
*   **Advanced RAG Pipeline:** Uses `all-minilm` for fast semantic search alongside BM25 sparse search for exact keyword matching (Reciprocal Rank Fusion). 
*   **Cross-Encoder Reranking & Strict Adherence:** Implements a lightning-fast Cross-Encoder (`ms-marco-MiniLM-L-6-v2`) to intelligently pinpoint the 3 most accurate paragraphs before handing them to the AI. Strict system prompts guarantee zero hallucinations—if the text doesn't contain the answer, the Maester will strictly refuse to guess.
*   **Local LLM Generation:** Uses `qwen2.5:1.5b` (or your preferred local model) to generate highly accurate, contextual answers.

## Prerequisites

Before you begin, ensure you have the following installed on your system:
*   **Python 3.8+**
*   **[Ollama](https://ollama.com/)** (for running the local LLM and embedding models)

## Setup Instructions

### 1. Clone or Download the Repository
Navigate to the project directory in your terminal:
```bash
cd path/to/Course Helper
```

### 2. Set Up a Virtual Environment (Recommended)
Create and activate a Python virtual environment to manage dependencies:

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies
Install the required packages using `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 4. Set Up Ollama and Pull Required Models
Ensure the Ollama application is running on your machine. Then, open a terminal and pull the necessary local models:

```bash
ollama pull all-minilm
ollama pull qwen2.5:1.5b
```

### 5. Configure Environment Variables
Create a file named `.env` in the root directory of the project (if it doesn't already exist). 

```env
# Flask Configuration
FLASK_DEBUG=1
FLASK_PORT=5000

# Ollama Configuration (local models)
OLLAMA_HOST=http://localhost:11434
EMBEDDING_MODEL=all-minilm
FALLBACK_LLM_MODEL=qwen2.5:1.5b
```

## Running the Application

1.  **Ensure Ollama is running** in the background.
2.  **Activate your virtual environment** (if it isn't already activated).
3.  **Start the Flask development server** by running:
    ```bash
    python run.py
    ```
4.  Open your web browser and navigate to `http://localhost:5000` to consult the archives.
