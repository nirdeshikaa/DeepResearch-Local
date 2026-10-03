"use strict";

/* ==========================================================
   DeepResearch Frontend
   ========================================================== */

const API_BASE = "";


/* ==========================================================
   DOM REFERENCES
   ========================================================== */

const systemStatus = document.getElementById("systemStatus");
const systemStatusText = document.getElementById("systemStatusText");
const chunkCount = document.getElementById("chunkCount");

const queryForm = document.getElementById("queryForm");
const queryInput = document.getElementById("queryInput");
const askButton = document.getElementById("askButton");

const loadingState = document.getElementById("loadingState");
const errorMessage = document.getElementById("errorMessage");

const answerSection = document.getElementById("answerSection");
const answerText = document.getElementById("answerText");
const sourcesList = document.getElementById("sourcesList");

const dropZone = document.getElementById("dropZone");
const pdfInput = document.getElementById("pdfInput");
const chooseFileButton = document.getElementById("chooseFileButton");

const uploadProgress = document.getElementById("uploadProgress");
const uploadResult = document.getElementById("uploadResult");


/* ==========================================================
   HELPERS
   ========================================================== */

function show(element) {
    element.classList.remove("hidden");
}

function hide(element) {
    element.classList.add("hidden");
}

function setQueryLoading(isLoading) {
    askButton.disabled = isLoading;
    queryInput.disabled = isLoading;

    if (isLoading) {
        show(loadingState);
        askButton.querySelector("span").textContent = "Working...";
    } else {
        hide(loadingState);
        askButton.querySelector("span").textContent = "Ask DeepResearch";
    }
}

function clearQueryError() {
    errorMessage.textContent = "";
    hide(errorMessage);
}

function showQueryError(message) {
    errorMessage.textContent = message;
    show(errorMessage);
}

function formatInteger(value) {
    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "—";
    }

    return number.toLocaleString();
}

async function parseErrorResponse(response) {
    try {
        const data = await response.json();

        if (typeof data.detail === "string") {
            return data.detail;
        }

        return `Request failed with status ${response.status}.`;

    } catch {
        return `Request failed with status ${response.status}.`;
    }
}


/* ==========================================================
   SYSTEM HEALTH
   ========================================================== */

async function loadSystemHealth() {
    try {
        const response = await fetch(`${API_BASE}/api/health`);

        if (!response.ok) {
            throw new Error(
                `Health check failed with status ${response.status}`
            );
        }

        const data = await response.json();

        systemStatusText.textContent = "System ready";
        systemStatus.classList.remove("offline");

        /*
         * The backend may expose the index count using one of these
         * names. If it does not yet expose a count, we leave the
         * visual value as an em dash rather than inventing one.
         */
        const count =
            data.total_chunks ??
            data.chunks ??
            data.vectors ??
            data.index_size;

        if (count !== undefined && count !== null) {
            chunkCount.textContent = formatInteger(count);
        }

    } catch (error) {
        console.error("Health check failed:", error);

        systemStatusText.textContent = "Backend unavailable";
        systemStatus.classList.add("offline");

        chunkCount.textContent = "—";
    }
}


/* ==========================================================
   RESEARCH QUERY
   ========================================================== */

queryForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    clearQueryError();
    hide(answerSection);

    const query = queryInput.value.trim();

    if (!query) {
        showQueryError("Enter a research question first.");
        queryInput.focus();
        return;
    }

    setQueryLoading(true);

    try {
        const response = await fetch(`${API_BASE}/api/query`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                query: query
            })
        });

        if (!response.ok) {
            const message = await parseErrorResponse(response);
            throw new Error(message);
        }

        const data = await response.json();

        if (!data.answer || !data.answer.trim()) {
            throw new Error(
                "The local model returned an empty response."
            );
        }

        renderAnswer(data.answer, data.sources || []);

        show(answerSection);

        answerSection.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });

    } catch (error) {
        console.error("Research query failed:", error);

        showQueryError(
            error.message ||
            "The research request could not be completed."
        );

    } finally {
        setQueryLoading(false);
    }
});


function renderAnswer(answer, sources) {
    /*
     * textContent is intentional.
     * Model output is treated as text, not executable HTML.
     */
    answerText.textContent = answer;

    sourcesList.replaceChildren();

    if (!Array.isArray(sources) || sources.length === 0) {
        const empty = document.createElement("p");
        empty.textContent = "No retrieved source metadata was returned.";
        empty.className = "source-disclaimer";

        sourcesList.appendChild(empty);
        return;
    }

    // Display each PDF only once.
    // Multiple passages from the same PDF can still be used by RAG.
    const uniqueSources = Array.from(
        new Map(
            sources.map(source => [
                source.source || source.filename || "Unknown source",
                source
            ])
        ).values()
    );

    uniqueSources.forEach((source, index) => {
        const item = document.createElement("div");
        item.className = "source-item";

        const rank = document.createElement("span");
        rank.className = "source-rank";
        rank.textContent = String(index + 1);

        const details = document.createElement("div");

        const sourceName =
    source.source ||
    source.filename ||
    "Unknown source";

const filename = document.createElement("a");
filename.textContent = sourceName + "  ↗ Open PDF";
filename.href = `/api/papers/${encodeURIComponent(sourceName)}`;
filename.target = "_blank";
filename.rel = "noopener noreferrer";
filename.className = "source-link";
filename.title = "Open source PDF";

filename.style.display = "inline-block";
filename.style.cursor = "pointer";
filename.style.textDecoration = "underline";
filename.style.fontWeight = "700";

        const note = document.createElement("span");

        if (
            source.distance !== undefined &&
            source.distance !== null &&
            Number.isFinite(Number(source.distance))
        ) {
            note.textContent =
                `Retrieved passage · L2 distance ${Number(
                    source.distance
                ).toFixed(3)}`;
        } else {
            note.textContent = "Retrieved passage";
        }

        details.appendChild(filename);
        details.appendChild(note);

        item.appendChild(rank);
        item.appendChild(details);

        sourcesList.appendChild(item);
    });
}


/* ==========================================================
   PDF SELECTION
   ========================================================== */

chooseFileButton.addEventListener("click", (event) => {
    event.stopPropagation();
    pdfInput.click();
});

dropZone.addEventListener("click", (event) => {
    if (event.target !== chooseFileButton) {
        pdfInput.click();
    }
});

pdfInput.addEventListener("change", () => {
    const file = pdfInput.files?.[0];

    if (file) {
        uploadPdf(file);
    }
});


/* ==========================================================
   DRAG AND DROP
   ========================================================== */

["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();

        dropZone.classList.add("drag-active");
    });
});

["dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();

        dropZone.classList.remove("drag-active");
    });
});

dropZone.addEventListener("drop", (event) => {
    const files = event.dataTransfer?.files;

    if (!files || files.length === 0) {
        return;
    }

    uploadPdf(files[0]);
});


/* ==========================================================
   PDF UPLOAD
   ========================================================== */

async function uploadPdf(file) {
    hide(uploadResult);

    if (!file) {
        return;
    }

    const isPdf =
        file.type === "application/pdf" ||
        file.name.toLowerCase().endsWith(".pdf");

    if (!isPdf) {
        showUploadResult(
            "Only PDF files are supported.",
            false
        );
        return;
    }

    chooseFileButton.disabled = true;
    show(uploadProgress);

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch(`${API_BASE}/api/upload`, {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            const message = await parseErrorResponse(response);
            throw new Error(message);
        }

        const data = await response.json();

        const pages = formatInteger(data.pages);
        const added = formatInteger(data.chunks_added);
        const total = formatInteger(data.total_chunks);

        showUploadResult(
            `${data.filename} was indexed successfully. ` +
            `${pages} pages produced ${added} searchable chunks. ` +
            `The knowledge base now contains ${total} chunks.`,
            true
        );

        if (data.total_chunks !== undefined) {
            chunkCount.textContent =
                formatInteger(data.total_chunks);
        }

    } catch (error) {
        console.error("PDF upload failed:", error);

        showUploadResult(
            error.message ||
            "The PDF could not be indexed.",
            false
        );

    } finally {
        hide(uploadProgress);
        chooseFileButton.disabled = false;

        /*
         * Reset so selecting the same file again still fires
         * the change event and lets the backend reject duplicates.
         */
        pdfInput.value = "";
    }
}


function showUploadResult(message, success) {
    uploadResult.replaceChildren();

    const heading = document.createElement("strong");
    heading.textContent =
        success
            ? "Paper indexed successfully"
            : "Upload could not be completed";

    const description = document.createElement("p");
    description.textContent = message;

    uploadResult.appendChild(heading);
    uploadResult.appendChild(description);

    uploadResult.classList.toggle(
        "upload-success",
        success
    );

    uploadResult.classList.toggle(
        "upload-success",
        success
    );

    uploadResult.classList.toggle(
        "upload-error",
        !success
    );

    show(uploadResult);
}


/* ==========================================================
   INITIALISE
   ========================================================== */

document.addEventListener("DOMContentLoaded", () => {
    loadSystemHealth();
});
