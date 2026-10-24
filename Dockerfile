# Meal-prep diary server + React SPA.
# Build:  docker build -t meal-prep .
# Serve:  docker run --rm -p 8000:8000 \
#           -v "$PWD/diary:/app/diary" \
#           -v "$PWD/logs:/app/logs" \
#           meal-prep
# Reference data (data/, recipes/) is baked into the image; only writable
# state (diary weeks, server logs) is mounted. Pull + redeploy for updates.
# Logs go to stdout (docker logs) and to /app/logs/diary-server.log.

# ---- UI build ----
FROM node:24-slim AS ui
WORKDIR /build/ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
RUN npm run build

# ---- Python runtime ----
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
# Third-party deps first, from pyproject.toml (single source of truth).
# Cached unless pyproject.toml changes; code changes below don't rerun it.
RUN --mount=type=cache,target=/root/.cache/pip \
    python - <<'EOF'
import subprocess
import sys
import tomllib
deps = tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]
subprocess.check_call([sys.executable, "-m", "pip", "install", *deps])
EOF
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY recipes/ ./recipes/
# UI bundle built above -> served by FastAPI StaticFiles mount.
COPY --from=ui /build/src/meal_prep/server/static/ ./src/meal_prep/server/static/
# Link the package itself without touching deps (cheap, reruns on code change).
RUN pip install --no-deps --no-cache-dir -e .
EXPOSE 8000
ENTRYPOINT ["python", "scripts/serve_diary.py"]
CMD ["--data-dir", "/app/data", "--recipes-dir", "/app/recipes", \
     "--diary-dir", "/app/diary", "--log-dir", "/app/logs", \
     "--host", "0.0.0.0", "--port", "8000"]
