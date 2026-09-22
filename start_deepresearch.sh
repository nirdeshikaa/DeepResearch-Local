#!/bin/bash

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODEL="$PROJECT_DIR/models/deepresearch-q4_k_m.gguf"

LLAMA_PORT=8081
APP_PORT=8000

cd "$PROJECT_DIR"

echo "========================================"
echo " DeepResearch Local"
echo "========================================"

if [ ! -f "$MODEL" ]; then
    echo "ERROR: Model not found:"
    echo "$MODEL"
    exit 1
fi

cleanup() {
    echo ""
    echo "Stopping DeepResearch..."

    if [ -n "${LLAMA_PID:-}" ]; then
        kill "$LLAMA_PID" 2>/dev/null || true
        wait "$LLAMA_PID" 2>/dev/null || true
    fi

    echo "DeepResearch stopped."
}

trap cleanup EXIT INT TERM

# Prevent confusing port conflicts.
if lsof -tiTCP:$LLAMA_PORT -sTCP:LISTEN >/dev/null 2>&1; then
    echo "ERROR: Port $LLAMA_PORT is already in use."
    echo "Stop the existing llama-server first."
    exit 1
fi

if lsof -tiTCP:$APP_PORT -sTCP:LISTEN >/dev/null 2>&1; then
    echo "ERROR: Port $APP_PORT is already in use."
    echo "Stop the existing FastAPI server first."
    exit 1
fi

echo ""
echo "[1/2] Starting local Qwen model..."

llama-server \
    -m "$MODEL" \
    --host 127.0.0.1 \
    --port $LLAMA_PORT \
    -c 4096 \
    -t 4 \
    > "$PROJECT_DIR/llama-server.log" 2>&1 &

LLAMA_PID=$!

echo "Waiting for model server..."

MODEL_READY=0

for i in {1..60}; do
    if curl -fsS "http://127.0.0.1:$LLAMA_PORT/health" >/dev/null 2>&1; then
        MODEL_READY=1
        break
    fi

    if ! kill -0 "$LLAMA_PID" 2>/dev/null; then
        echo "ERROR: llama-server stopped unexpectedly."
        echo "Check llama-server.log"
        exit 1
    fi

    sleep 1
done

if [ "$MODEL_READY" -ne 1 ]; then
    echo "ERROR: Model server did not become ready."
    echo "Check llama-server.log"
    exit 1
fi

echo "Model server ready."

echo ""
echo "[2/2] Starting DeepResearch web application..."
echo ""
echo "Open:"
echo "http://127.0.0.1:$APP_PORT"
echo ""
echo "Press Ctrl+C to stop DeepResearch."
echo "========================================"
echo ""

exec uvicorn backend.main:app \
    --host 127.0.0.1 \
    --port $APP_PORT
