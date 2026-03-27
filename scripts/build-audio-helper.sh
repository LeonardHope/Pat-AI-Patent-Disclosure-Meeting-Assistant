#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
HELPER_DIR="$PROJECT_DIR/audio-helper"

echo "Building audio helper..."
cd "$HELPER_DIR"
swift build -c release

# Copy binary to a known location
BINARY_PATH="$(swift build -c release --show-bin-path)/AudioCapture"
cp "$BINARY_PATH" "$PROJECT_DIR/audio-helper/AudioCapture"

echo "Built: $PROJECT_DIR/audio-helper/AudioCapture"
echo ""
echo "Usage:"
echo "  ./audio-helper/AudioCapture              # Capture all system audio"
echo "  ./audio-helper/AudioCapture --list        # List apps"
echo "  ./audio-helper/AudioCapture --app zoom.us # Capture Zoom audio"
