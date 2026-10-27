#!/usr/bin/env bash
# Smoke-test a built deploy image: start it, then check health, the UI, the
# catalog API and that logging a diary entry writes a week file.
#
# Usage: scripts/smoke_image.sh [IMAGE] (default meal-prep:ci)
#   PORT=8000 scripts/smoke_image.sh meal-prep:ci
#
# CI runs this after `docker build` (.github/workflows/image.yml). What the
# smoke test checks lives here, in normal code review, not in the workflow.
# The diary and logs go to a throwaway directory; the container's output is
# printed and the container removed on exit, pass or fail.
set -euo pipefail

image="${1:-meal-prep:ci}"
port="${PORT:-8000}"
base="http://127.0.0.1:${port}"
name="meal-prep-smoke-$$"
work="$(mktemp -d)"
mkdir -p "$work/diary" "$work/logs"

cleanup() {
  echo "--- container logs ---"
  docker logs "$name" 2>&1 || true
  docker rm -f "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# The container runs as uid 1000 and must be able to write both mounts.
if [ "$(id -u)" -eq 0 ]; then
  chown 1000:1000 "$work/diary" "$work/logs"
else
  sudo chown 1000:1000 "$work/diary" "$work/logs"
fi

docker run -d --name "$name" -p "127.0.0.1:${port}:8000" \
  -v "$work/diary:/app/diary" -v "$work/logs:/app/logs" "$image" >/dev/null

for _ in $(seq 1 30); do
  curl -fs "$base/api/health" >/dev/null && break
  sleep 1
done

echo "health";  curl -fs "$base/api/health" >/dev/null
echo "ui";      curl -fs "$base/" | grep -q '<div id="root">'
echo "catalog"; curl -fs "$base/api/catalog" >/dev/null
echo "diary";   curl -fs -X POST -H 'Content-Type: application/json' \
  -d '{"date":"2026-10-26","mealtime":"breakfast","recipe":"flat-white"}' \
  "$base/api/diary/2026-W44/entries" >/dev/null
test -f "$work/diary/2026-W44.yaml"
echo "smoke test passed"
