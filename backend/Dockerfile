# =============================================================================
# AI-Powered Leaflet Data Extraction Platform
# Backend Dockerfile
# =============================================================================

# Build stage
# Using Python 3.12 for PaddlePaddle/PaddleOCR compatibility
FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt


# Production stage
FROM python:3.12-slim AS production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Create non-root user for security with home directory
RUN groupadd -r appgroup && useradd -r -g appgroup -m -d /home/appuser appuser

# Create app directory and set permissions
WORKDIR /app
RUN mkdir -p /app/storage /app/logs /home/appuser/.paddleocr /home/appuser/.cache && \
    chown -R appuser:appgroup /app /home/appuser

# Set PaddleOCR cache directory and disable PIR/oneDNN for PaddlePaddle 3.x compatibility
# Also limit threading to avoid race conditions in forked processes
ENV HOME=/home/appuser \
    PADDLEOCR_HOME=/home/appuser/.paddleocr \
    FLAGS_use_mkldnn=0 \
    FLAGS_enable_pir_api=0 \
    FLAGS_enable_pir_in_executor=0 \
    FLAGS_pir_apply_inplace_pass=0 \
    FLAGS_allocator_strategy=naive_best_fit \
    FLAGS_cpu_deterministic=true \
    FLAGS_inner_op_parallelism=1 \
    MKLDNN_CACHE_CAPACITY=0 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    GLOG_v=0 \
    DISABLE_MODEL_SOURCE_CHECK=True

# Copy application code
COPY --chown=appuser:appgroup . .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]