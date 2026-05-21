#!/usr/bin/env bash
set -Eeuo pipefail

echo "Stopping Duckling..."
docker compose stop duckling || true

echo "Done."
