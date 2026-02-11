FROM python:3.11-slim AS base

WORKDIR /app

# Install uv for fast pip
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python deps
COPY pyproject.toml .
RUN uv pip install --system -e ".[serving]"

# Copy source
COPY src/ src/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["uvicorn", "wine_rec.serving.app:app", "--host", "0.0.0.0", "--port", "8000"]
