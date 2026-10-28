FROM python:3.12-slim

WORKDIR /app

# Install system deps for asyncpg and Pillow
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip install --no-cache-dir ".[dev]"

# Default: run the API server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
