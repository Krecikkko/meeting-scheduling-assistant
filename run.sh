#!/usr/bin/env bash
#
# Usage: ./run.sh [options]
#
# This script starts the Duckling entity extractor container, validates
# Rasa training data, trains the model (optional), launches the custom
# action server in the background, and starts the interactive Rasa shell.
#
# Available Options:
#   --stop-duckling    Stop the Duckling container when exiting the script.
#                      By default, Duckling is left running.
#   --skip-train       Skip model training (rasa train) and start the Rasa
#                      shell directly using the last trained model.
#
set -Eeuo pipefail

STOP_DUCKLING=false
SKIP_TRAIN=false

for arg in "$@"; do
  case "$arg" in
    --stop-duckling)
      STOP_DUCKLING=true
      ;;
    --skip-train)
      SKIP_TRAIN=true
      ;;
    *)
      echo "Unknown option: $arg"
      echo "Available options: --stop-duckling --skip-train"
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

ACTION_PID=""

cleanup() {
  echo ""
  echo "Cleaning up..."

  if [ -n "${ACTION_PID}" ] && kill -0 "$ACTION_PID" 2>/dev/null; then
    echo "Stopping Rasa action server..."
    kill "$ACTION_PID" 2>/dev/null || true
  fi

  if [ "$STOP_DUCKLING" = true ]; then
    echo "Stopping Duckling..."
    docker compose stop duckling || true
  fi

  echo "Done."
}

trap cleanup EXIT INT TERM

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

echo "Starting action server..."
rasa run actions &
ACTION_PID=$!
sleep 3

echo "Starting Rasa shell..."
rasa shell