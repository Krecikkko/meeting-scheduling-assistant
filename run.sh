#!/usr/bin/env bash
#
# Usage: ./run.sh [options]
#
# This script starts the Duckling entity extractor container, validates
# Rasa training data, trains the model (optional), launches the custom
# action server, Rasa REST server, and python static server in the background,
# and opens the browser to point to the chat client.
#
# Available Options:
#   --stop-duckling    Stop the Duckling container when exiting the script.
#                      By default, Duckling is left running.
#   --skip-train       Skip model training (rasa train) and start the Rasa
#                      server directly using the last trained model.
#   --no-browser       Do not automatically open the browser page.
#
set -Eeuo pipefail

STOP_DUCKLING=false
SKIP_TRAIN=false
NO_BROWSER=false

for arg in "$@"; do
  case "$arg" in
    --stop-duckling)
      STOP_DUCKLING=true
      ;;
    --skip-train)
      SKIP_TRAIN=true
      ;;
    --no-browser)
      NO_BROWSER=true
      ;;
    *)
      echo "Unknown option: $arg"
      echo "Available options: --stop-duckling --skip-train --no-browser"
      exit 1
      ;;
  esac
done

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [ -f ".venv/bin/activate" ]; then
  source ".venv/bin/activate"
else
  echo "No .venv found. Create it first with:"
  echo "python3.10 -m venv .venv"
  echo "source .venv/bin/activate"
  echo "pip install -r requirements.txt"
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "WARNING: .env file not found! Please copy .env.example to .env and fill in your Home Assistant configuration."
  echo "Continuing without Home Assistant calendar sync..."
  echo ""
fi

# Ensure runtime directory exists
mkdir -p .runtime

cleanup() {
  echo ""
  echo "Cleaning up background processes..."

  # Stop action server
  if [ -f ".runtime/action.pid" ]; then
    PID=$(cat .runtime/action.pid 2>/dev/null || true)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
      echo "Stopping Rasa action server (PID $PID)..."
      kill "$PID" 2>/dev/null || true
    fi
    rm -f .runtime/action.pid
  fi

  # Stop Rasa server
  if [ -f ".runtime/rasa.pid" ]; then
    PID=$(cat .runtime/rasa.pid 2>/dev/null || true)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
      echo "Stopping Rasa REST server (PID $PID)..."
      kill "$PID" 2>/dev/null || true
    fi
    rm -f .runtime/rasa.pid
  fi

  # Stop static web server
  if [ -f ".runtime/web.pid" ]; then
    PID=$(cat .runtime/web.pid 2>/dev/null || true)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
      echo "Stopping web server (PID $PID)..."
      kill "$PID" 2>/dev/null || true
    fi
    rm -f .runtime/web.pid
  fi

  # Stop Duckling
  if [ "$STOP_DUCKLING" = true ]; then
    echo "Stopping Duckling..."
    docker compose stop duckling || true
  fi

  rmdir .runtime 2>/dev/null || true
  echo "Done."
}

trap cleanup EXIT INT TERM

# Free ports if they are already in use to prevent start conflicts
for port in 5005 5055 8080; do
  if lsof -i :$port >/dev/null 2>&1; then
    echo "Port $port is in use. Killing the existing process..."
    kill -9 $(lsof -t -i:$port) 2>/dev/null || true
    sleep 1
  fi
done

echo "Starting Duckling with Docker Compose..."
docker compose up -d duckling

echo "Checking Duckling..."
sleep 2
curl -s -XPOST http://localhost:8000/parse \
  --data 'locale=en_GB&text=tomorrow at 8' >/dev/null || {
    echo "Duckling is not responding on http://localhost:8000"
    exit 1
  }

echo "Duckling is running."

echo "Validating Rasa data..."
rasa data validate

if [ "$SKIP_TRAIN" = false ]; then
  echo "Training Rasa model..."
  rasa train
else
  echo "Skipping training."
fi

echo "Starting Rasa action server..."
rasa run actions --port 5055 > action_server.log 2>&1 &
echo $! > .runtime/action.pid
sleep 3

echo "Starting Rasa REST server..."
rasa run --enable-api --cors "*" --port 5005 > rasa_server.log 2>&1 &
echo $! > .runtime/rasa.pid
sleep 5

echo "Starting static web server..."
python3 -m http.server 8080 --directory web > web_server.log 2>&1 &
echo $! > .runtime/web.pid
sleep 2

echo ""
echo "=========================================================="
echo "Assistant is up and running!"
echo "--------------------------------------------------------=="
echo "  - Chat UI:        http://localhost:8080"
echo "  - Rasa REST API:  http://localhost:5005"
echo "  - Action server:  http://localhost:5055"
echo "  - Duckling:       http://localhost:8000"
echo "=========================================================="
echo ""

if [ "$NO_BROWSER" = false ]; then
  if command -v xdg-open >/dev/null 2>&1; then
    echo "Opening Chat UI in browser..."
    xdg-open "http://localhost:8080" || true
  elif command -v open >/dev/null 2>&1; then
    echo "Opening Chat UI in browser..."
    open "http://localhost:8080" || true
  fi
fi

echo "Press Ctrl+C to stop all services."

# Keep running
while true; do
  sleep 1
done