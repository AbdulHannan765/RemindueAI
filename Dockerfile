
# ==============================================================================
# Dockerfile - RemindueAI (Render Deployment)
# ==============================================================================

FROM python:3.13-slim

# ------------------------------------------------------------------------------
# Environment variables
# ------------------------------------------------------------------------------

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    HOME=/tmp \
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed \
    HF_HOME=/app/.cache/huggingface \
    PIP_NO_CACHE_DIR=1

# ------------------------------------------------------------------------------
# Install system dependencies
# ------------------------------------------------------------------------------

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# Application directory
# ------------------------------------------------------------------------------

WORKDIR /app

# ------------------------------------------------------------------------------
# Create non-root application user
# ------------------------------------------------------------------------------

RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 --no-create-home appuser && \
    mkdir -p \
        /app/.cache/fastembed \
        /app/.cache/huggingface && \
    chown -R appuser:appgroup /app

# ------------------------------------------------------------------------------
# Install Python dependencies
# ------------------------------------------------------------------------------

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------------------------
# Verify spaCy model installation
#
# requirements.txt should install:
# en_core_web_lg==3.8.0
# ------------------------------------------------------------------------------

RUN python -c "import spacy; spacy.load('en_core_web_lg'); print('spaCy large model loaded successfully')"

# ------------------------------------------------------------------------------
# Download FastEmbed model during image build
# ------------------------------------------------------------------------------

RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')"

# ------------------------------------------------------------------------------
# Copy application source code
# ------------------------------------------------------------------------------

COPY . .

# ------------------------------------------------------------------------------
# Set permissions for non-root execution
# ------------------------------------------------------------------------------

RUN chown -R appuser:appgroup /app

# ------------------------------------------------------------------------------
# Run application as non-root user
# ------------------------------------------------------------------------------

USER appuser

# ------------------------------------------------------------------------------
# Render port
# ------------------------------------------------------------------------------

EXPOSE 10000

# ------------------------------------------------------------------------------
# Start FastAPI
# ------------------------------------------------------------------------------

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
