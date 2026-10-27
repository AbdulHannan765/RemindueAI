
# ==============================================================================
# Dockerfile - RemindueAI (Render Deployment)
# ==============================================================================

FROM python:3.13-slim

# Python and application environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed \
    HF_HOME=/app/.cache/huggingface

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Application directory
WORKDIR /app

# Create non-root user and cache directories
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 --no-create-home appuser && \
    mkdir -p /app/.cache/fastembed /app/.cache/huggingface && \
    chown -R appuser:appgroup /app

# Install dependencies first for Docker layer caching
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Download the FastEmbed model during image build
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')"

# Copy application source code
COPY . .

# Set permissions
RUN chown -R appuser:appgroup /app

# Run as non-root user
USER appuser

EXPOSE 10000

# Start FastAPI
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
