# Meal-prep diary server + React SPA, and the CI checks that gate it.
#
# This file is the single source of toolchain versions (Python, Node, uv):
# CI runs everything through it instead of installing its own copies.
#   docker build --target test .   ruff, mypy, pytest (CI job `check`)
#   docker build --target ui .     UI lint, typecheck, build (CI job `ui`)
#   docker build .                 the deploy image (CI job `image`, which
#                                  smoke-tests it and publishes it on master
#                                  as ghcr.io/neantonii/meal-prep)
#
# Stages: `test` and the final runtime stage are siblings built on the same
# `deps` stage, so the tests run against exactly the server packages that
# ship. Dev tools, the planner group and the tests never reach the runtime
# image; neither do uv, node or any package cache.
#
# Pinning: every image by digest (Dependabot's docker ecosystem proposes
# updates after the cooldown in .github/dependabot.yml), Python packages from
# uv.lock, npm packages from ui/package-lock.json.

# ---- uv (tool image; only its binary is used) ----
FROM ghcr.io/astral-sh/uv:0.12.18@sha256:3adc3706091ce7c2fe595e669628caedd6d951551b92b258b7e7dbe06d9440bc AS uv

# ---- UI: lint, typecheck, bundle ----
FROM node:26-slim@sha256:36793bcbb160a6a16cede1e62b93f84e26b78a972a8a4c0b879c1c12f22761ec AS ui
WORKDIR /build/ui
COPY ui/package.json ui/package-lock.json ui/.npmrc ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
# `npm run build` typechecks (tsc -b) and writes the bundle to
# ../src/meal_prep/server/static/.
RUN npm run lint && npm run build

# ---- Python base (shared by the build stages and the runtime) ----
# The only place the Python image is named, so tests and server always run on
# the same interpreter.
FROM python:3.13-slim AS python-base

# ---- Python + uv (shared by deps and test) ----
FROM python-base AS python-uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH
WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv

# ---- Server packages, exactly as uv.lock pins them ----
FROM python-uv AS deps
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

# ---- CI gate: lint, types, tests (never shipped) ----
FROM deps AS test
# Adds the dev and planner groups on top of the server packages. (uv sync is
# exact: --no-install-project here would uninstall the project deps put in.)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked
COPY . .
RUN ruff check . \
    && ruff format --check . \
    && mypy \
    && pytest -q

# ---- Runtime (the deploy image) ----
FROM python-base
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
