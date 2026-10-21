# Meal-prep diary server + React SPA.
# Build:  docker build -t meal-prep .
# Serve:  docker run --rm -p 8000:8000 \
#           -v "$PWD/data:/app/data:ro" \
#           -v "$PWD/recipes:/app/recipes:ro" \
#           -v "$PWD/diary:/app/diary" \
#           -v "$PWD/logs:/app/logs" \
#           meal-prep
# Data dirs are mounted at runtime; the image only carries code + built UI.
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
RUN pip install --no-cache-dir -e . "fastapi>=0.115" "uvicorn>=0.30"
COPY src/ ./src/
COPY scripts/ ./scripts/
# UI bundle built above -> served by FastAPI StaticFiles mount.
COPY --from=ui /build/src/meal_prep/server/static/ ./src/meal_prep/server/static/
EXPOSE 8000
ENTRYPOINT ["python", "scripts/serve_diary.py"]
CMD ["--data-dir", "/app/data", "--recipes-dir", "/app/recipes", \
     "--diary-dir", "/app/diary", "--log-dir", "/app/logs", \
     "--host", "0.0.0.0", "--port", "8000"]
