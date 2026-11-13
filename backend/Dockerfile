FROM python:3.13-slim

# uv, pinned to the same version used on the host (research R2).
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

# The virtualenv lives outside /app: docker-compose mounts ./backend over /app for live reload,
# which would otherwise hide the container's installed packages behind the host's .venv.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# WeasyPrint's system libraries (Pango for text layout, HarfBuzz subsetting for small font files)
# and a font with "§" and "–", for the PDF exports (feature 008, research R6; about 70 MB).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install the exact versions from uv.lock first, so this layer is cached until the lock changes.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
