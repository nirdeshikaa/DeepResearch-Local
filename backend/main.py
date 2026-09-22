from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.services.rag_service import RAGService, build_rag_prompt
from backend.services.model_service import ModelService


rag_service = None
model_service = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_service, model_service

    print("Starting DeepResearch services...")

    rag_service = RAGService()
    model_service = ModelService()

    print("DeepResearch services ready.")

    yield

    print("Shutting down DeepResearch services...")


app = FastAPI(
    title="DeepResearch API",
    description="Local RAG research paper synthesis backend",
    version="1.0.0",
    lifespan=lifespan,
)


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class QueryRequest(BaseModel):
    query: str



# ============================================================
# FRONTEND
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="static",
)


@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health_check():
    total_chunks = (
        int(rag_service.index.ntotal)
        if rag_service is not None
        else 0
    )

    return {
        "status": "ok",
        "service": "DeepResearch",
        "backend": "FastAPI",
        "mode": "local",
        "rag_ready": rag_service is not None,
        "model_ready": model_service is not None,
        "total_chunks": total_chunks,
    }


@app.post("/api/search")
def search_papers(request: SearchRequest):
    if rag_service is None:
        raise HTTPException(
            status_code=503,
            detail="RAG service is not ready."
        )

    try:
        results = rag_service.retrieve(
            query=request.query,
            top_k=request.top_k
        )

        return {
            "query": request.query,
            "count": len(results),
            "results": results,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception as exc:
        print(f"Retrieval error: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Research paper retrieval failed."
        )


@app.post("/api/query")
def query_deepresearch(request: QueryRequest):
    if rag_service is None or model_service is None:
        raise HTTPException(
            status_code=503,
            detail="DeepResearch services are not ready."
        )

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    try:
        # 1. Retrieve research evidence
        results = rag_service.retrieve(
            query=query,
            top_k=5
        )

        # 2. Build grounded prompt
        prompt = build_rag_prompt(
            query=query,
            results=results
        )

        # 3. Generate with local Qwen2.5 + merged LoRA
        answer = model_service.generate(
            prompt=prompt,
            max_tokens=256,
            temperature=0.2
        )

        # 4. Return answer + real retrieved sources
        sources = [
            {
                "rank": result["rank"],
                "source": result["source"],
                "distance": result["distance"],
            }
            for result in results
        ]

        return {
            "query": query,
            "answer": answer,
            "sources": sources,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except RuntimeError as exc:
        print(f"Generation error: {exc}")
        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )

    except Exception as exc:
        print(f"Unexpected query error: {exc}")
        raise HTTPException(
            status_code=500,
            detail="DeepResearch query failed."
        )


# ============================================================
# PDF UPLOAD
# ============================================================

import shutil
import tempfile

from fastapi import UploadFile, File

from backend.services.pdf_service import extract_pdf
from backend.services.rag_service import ingest_chunks


@app.post("/api/upload")
def upload_pdf(file: UploadFile = File(...)):
    if rag_service is None:
        raise HTTPException(
            status_code=503,
            detail="RAG service is not ready."
        )

    filename = Path(file.filename or "").name

    if not filename:
        raise HTTPException(
            status_code=400,
            detail="A filename is required."
        )

    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported."
        )

    temp_path = None

    try:
        # Save upload temporarily.
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf"
        ) as temp_file:

            shutil.copyfileobj(
                file.file,
                temp_file
            )

            temp_path = Path(temp_file.name)

        # Validate + extract + chunk.
        pdf = extract_pdf(temp_path)

        # Persist uploaded PDF only after successful validation.
        papers_dir = Path(__file__).resolve().parents[1] / "data" / "papers"
        papers_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        destination = papers_dir / filename

        if destination.exists():
            raise ValueError(
                f"This PDF is already stored: {filename}"
            )

        # Add chunks to FAISS + metadata.
        ingestion = ingest_chunks(
            service=rag_service,
            filename=filename,
            chunks=pdf["chunks"]
        )

        shutil.copy2(
            temp_path,
            destination
        )

        return {
            "status": "success",
            "filename": filename,
            "pages": pdf["pages"],
            "chunks_added": ingestion["chunks_added"],
            "total_chunks": ingestion["vectors_after"],
            "index_aligned": ingestion["aligned"],
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception as exc:
        print(f"PDF upload error: {exc}")

        raise HTTPException(
            status_code=500,
            detail="PDF ingestion failed."
        )

    finally:
        try:
            file.file.close()
        except Exception:
            pass

        if temp_path and temp_path.exists():
            temp_path.unlink()
