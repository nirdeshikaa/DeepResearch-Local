from pathlib import Path

import fitz


CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
) -> list[str]:

    text = " ".join(text.split())

    chunks = []
    start = 0

    while start < len(text):
        end = min(
            start + chunk_size,
            len(text)
        )

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end == len(text):
            break

        start = end - overlap

    return chunks


def extract_pdf(file_path: str | Path) -> dict:
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"PDF file not found: {file_path}"
        )

    if file_path.suffix.lower() != ".pdf":
        raise ValueError(
            "Only PDF files are supported."
        )

    # Verify actual PDF signature, not only filename extension.
    with open(file_path, "rb") as f:
        signature = f.read(5)

    if signature != b"%PDF-":
        raise ValueError(
            "The uploaded file is not a valid PDF."
        )

    try:
        document = fitz.open(file_path)
    except Exception as exc:
        raise ValueError(
            "The PDF could not be opened."
        ) from exc

    try:
        page_count = document.page_count

        pages = []

        for page_number in range(page_count):
            page = document.load_page(page_number)
            text = page.get_text("text")

            if text and text.strip():
                pages.append(text)

        full_text = "\n".join(pages).strip()

    finally:
        document.close()

    if not full_text:
        raise ValueError(
            "No extractable text was found in the PDF."
        )

    chunks = chunk_text(full_text)

    if not chunks:
        raise ValueError(
            "The PDF did not produce any searchable text chunks."
        )

    return {
        "filename": file_path.name,
        "pages": page_count,
        "text": full_text,
        "chunks": chunks,
    }
