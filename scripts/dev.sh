#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Starting Disclosure Meeting Assistant (development mode)"
echo ""

# Kill any existing servers
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null || true

# Start Python backend
echo "Starting backend on :8000..."
cd "$PROJECT_DIR/sidecar"
uv run python main.py &
BACKEND_PID=$!

# Wait for backend to be ready
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8000/api/status > /dev/null 2>&1; then
        echo "Backend ready"
        break
    fi
    sleep 1
done

# Start frontend
echo "Starting frontend on :5173..."
cd "$PROJECT_DIR"
pnpm dev &
FRONTEND_PID=$!

echo ""
echo "Application running:"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop"

# Wait for either to exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
