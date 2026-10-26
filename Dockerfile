# Meal-prep diary server + React SPA in one image.
#
# CI builds and smoke-tests this on every PR and publishes it on every push to
# master (.github/workflows/image.yml) as ghcr.io/neantonii/meal-prep:latest
# and :sha-<commit>. Local build: docker build -t meal-prep .
#
# Three stages; only the last one ships. Build tools (node, npm, uv) and their
# caches stay in the build stages. The runtime stage gets the finished virtual
# env, the code, the reference data and the UI bundle.
#
# Pinning: base images by digest, Python packages from uv.lock (server deps
# only: no dev or planner groups), npm packages from ui/package-lock.json.
# Dependabot (docker ecosystem) proposes base image updates after the cooldown
# in .github/dependabot.yml. Node major == ui/.nvmrc and Python == CI
# (tests/test_deploy.py).

# ---- UI bundle ----
FROM node:26-slim@sha256:36793bcbb160a6a16cede1e62b93f84e26b78a972a8a4c0b879c1c12f22761ec AS ui
WORKDIR /build/ui
COPY ui/package.json ui/package-lock.json ui/.npmrc ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
# Vite writes the bundle to ../src/meal_prep/server/static/.
RUN npm run build

# ---- Python environment ----
FROM python:3.13-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962 AS deps
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.18
# Third-party packages first (layer cached until uv.lock changes), then the
# project itself as an editable install: the server serves the UI bundle from
# src/meal_prep/server/static/, which is not packaged, so the runtime stage
# keeps src/ at the same path the editable install points to.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-default-groups --no-install-project
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-default-groups

# ---- Runtime ----
FROM python:3.13-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962
LABEL org.opencontainers.image.source="https://github.com/neantonii/meal-prep"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH
WORKDIR /app
RUN useradd --uid 1000 --no-create-home app
COPY --from=deps /app/.venv/ ./.venv/
COPY src/ ./src/
COPY --from=ui /build/src/meal_prep/server/static/ ./src/meal_prep/server/static/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY recipes/ ./recipes/
# Host dirs mounted on /app/diary and /app/logs must be writable by uid 1000
# (see compose.example.yml).
RUN mkdir -p diary logs && chown app:app diary logs
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]
ENTRYPOINT ["python", "scripts/serve_diary.py"]
CMD ["--data-dir", "/app/data", "--recipes-dir", "/app/recipes", \
     "--diary-dir", "/app/diary", "--log-dir", "/app/logs", \
     "--host", "0.0.0.0", "--port", "8000"]
