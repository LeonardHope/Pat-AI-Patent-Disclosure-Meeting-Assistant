#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MODELS_DIR="$PROJECT_DIR/models"

MODEL_NAME="ggml-large-v3-turbo.bin"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/${MODEL_NAME}"
MODEL_PATH="$MODELS_DIR/$MODEL_NAME"

if [ -f "$MODEL_PATH" ]; then
    echo "Model already exists: $MODEL_PATH"
    exit 0
fi

echo "Downloading Whisper large-v3-turbo model (~1.5GB)..."
echo "From: $MODEL_URL"
echo "To:   $MODEL_PATH"
echo ""

mkdir -p "$MODELS_DIR"
curl -L --progress-bar "$MODEL_URL" -o "$MODEL_PATH.tmp"
mv "$MODEL_PATH.tmp" "$MODEL_PATH"

echo ""
echo "Done: $MODEL_PATH ($(du -h "$MODEL_PATH" | cut -f1))"
