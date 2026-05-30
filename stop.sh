#!/usr/bin/env bash
#
# Usage: ./stop.sh [options]
#
# This script reads saved process IDs from the .runtime/ folder, stops
# all background servers, and stops the Duckling container.
#
# Available Options:
#   --keep-duckling    Keep the Duckling Docker container running.
#                      By default, Duckling is stopped.
#
set -Eeuo pipefail

KEEP_DUCKLING=false

for arg in "$@"; do
  case "$arg" in
    --keep-duckling)
      KEEP_DUCKLING=true
      ;;
    *)
      echo "Unknown option: $arg"
      echo "Available options: --keep-duckling"
      exit 1
      ;;
  esac
done

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "Stopping background processes..."

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

# Try to remove runtime directory if empty
rmdir .runtime 2>/dev/null || true

if [ "$KEEP_DUCKLING" = false ]; then
  echo "Stopping Duckling..."
  docker compose stop duckling || true
else
  echo "Keeping Duckling running."
fi

echo "Done."
