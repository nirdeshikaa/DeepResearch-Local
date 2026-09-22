# DeepResearch Local

DeepResearch is a locally hosted academic research assistant that combines Retrieval-Augmented Generation (RAG) with a LoRA-adapted language model for research-paper exploration and synthesis.

The application supports semantic search over an indexed academic-paper collection, local question answering, and dynamic ingestion of new PDF documents.

## System Architecture

The local pipeline is:

User Interface → FastAPI → MiniLM Embeddings → FAISS Retrieval → Retrieved Research Context → Qwen2.5 + LoRA → Generated Answer + Retrieved Sources

### Main Components

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** FastAPI
- **Embedding model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Vector search:** FAISS
- **Language model:** Qwen2.5-1.5B-Instruct
- **Fine-tuning:** LoRA
- **Local inference:** llama.cpp / GGUF
- **PDF processing:** PyMuPDF

## Local Model

The final language model is based on `Qwen/Qwen2.5-1.5B-Instruct`.

The trained LoRA adapter was merged with the base model and converted to GGUF for CPU inference using Q4_K_M quantization.

The GGUF model is excluded from Git because it is a large binary artifact.

Expected local path:

    models/deepresearch-q4_k_m.gguf

## Retrieval-Augmented Generation

Research papers are split into overlapping text chunks and encoded using MiniLM embeddings. Their vectors are stored in a FAISS index.

For each research question:

1. The question is converted into an embedding.
2. FAISS retrieves the most semantically relevant chunks.
3. Retrieved text is supplied to the language model as context.
4. The local Qwen2.5 + LoRA model generates the answer.
5. The interface displays the retrieved source documents.

Displayed sources represent retrieved context and should not be interpreted as verified claim-level citations.

## Dynamic PDF Ingestion

New academic PDFs can be added directly through the web interface.

Pipeline:

    PDF Upload
        ↓
    PyMuPDF Text Extraction
        ↓
    Text Chunking
        ↓
    MiniLM Embeddings
        ↓
    FAISS Index Update
        ↓
    Metadata Persistence

Newly indexed documents become immediately searchable. Duplicate filenames are rejected to prevent accidental repeated ingestion.

## Running DeepResearch

### Requirements

- Python environment with the packages in `requirements.txt`
- `llama-server` from llama.cpp available on PATH
- Local GGUF model at `models/deepresearch-q4_k_m.gguf`

Install llama.cpp on macOS with Homebrew if required:

    brew install llama.cpp

### Start

Activate the environment:

    conda activate deepresearch

Enter the project directory:

    cd ~/DeepResearch_Local

Start the complete application:

    ./start_deepresearch.sh

The launcher starts the local model server on port 8081 and the FastAPI application on port 8000.

Open the application at:

    http://127.0.0.1:8000

Press `Ctrl+C` in the launcher terminal to stop the application.

## API Endpoints

- `GET /api/health` — application and knowledge-base status
- `POST /api/search` — semantic FAISS retrieval
- `POST /api/query` — complete RAG generation pipeline
- `POST /api/upload` — dynamic PDF ingestion

## Project Structure

    DeepResearch_Local/
    ├── backend/
    │   ├── main.py
    │   └── services/
    │       ├── embedding_service.py
    │       ├── model_service.py
    │       ├── pdf_service.py
    │       └── rag_service.py
    ├── frontend/
    │   ├── index.html
    │   ├── styles.css
    │   └── app.js
    ├── data/
    │   ├── index/
    │   └── papers/
    ├── models/
    ├── requirements.txt
    ├── start_deepresearch.sh
    ├── .gitignore
    └── README.md

Runtime FAISS data, uploaded PDFs, model weights, logs, and temporary conversion artifacts are intentionally excluded from Git.

## Validated Functionality

The prototype has been tested for:

- Local CPU model inference
- Semantic FAISS retrieval
- RAG-based question answering
- Frontend/backend integration
- Persistent FAISS and metadata storage
- PDF text extraction
- Dynamic PDF ingestion
- Duplicate-upload rejection
- Immediate retrieval from newly indexed PDFs
- Application restart and persistence

## Research Evaluation

Final held-out four-system ROUGE-L comparison:

| System | ROUGE-L |
| --- | ---: |
| Base Qwen | 0.1195 |
| Qwen + LoRA | 0.2223 |
| Qwen + RAG | 0.2114 |
| Qwen + LoRA + RAG | 0.2985 |

Additional evaluation:

- Retrieval Precision@5: **0.96**
- Mean claim-to-source cosine similarity: **0.5987**
- Human factual accuracy: **3.50 / 5**
- Human evidence relevance: **3.30 / 5**
- Human response coherence: **4.15 / 5**
- Overall human evaluation: **3.65 / 5**

Claim-to-source cosine similarity is a semantic-alignment heuristic and is not proof of factual entailment.

## Scope and Limitations

DeepResearch is a research prototype rather than a production multi-user platform.

Current limitations include:

- CPU generation is slower than GPU inference.
- Retrieved sources are contextual evidence, not verified inline citations.
- Duplicate detection currently uses filenames.
- The local application is primarily designed for single-user operation.
- Model weights and runtime research data are not stored in Git.

## Project Status

The core research system and local demonstrator are functionally complete.

The application demonstrates an end-to-end local workflow combining LoRA adaptation, semantic retrieval, dynamic document ingestion, persistent FAISS storage, and retrieval-augmented generation.
