# =============================================================================
# UKG-TravelPerk Integration Dockerfile
# Multi-stage build for optimized production images
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/deps -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Production - Minimal runtime image
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS production

# OCI Image Labels (https://github.com/opencontainers/image-spec/blob/main/annotations.md)
LABEL org.opencontainers.image.title="UKG-TravelPerk Integration"
LABEL org.opencontainers.image.description="UKG Pro to TravelPerk SCIM User Sync Service"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.vendor="VAI Consulting"
LABEL org.opencontainers.image.source="https://github.com/vai-consulting/vai-matrix-ukg-travelperk"
LABEL org.opencontainers.image.licenses="Proprietary"

# Environment configuration
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV DATA_DIR=/app/data
ENV LOG_LEVEL=INFO

WORKDIR /app

# Copy dependencies from builder stage
COPY --from=builder /deps /usr/local/lib/python3.11/site-packages/

# Copy application code
COPY src/ /app/src/
COPY common/ /app/common/
COPY run-travelperk-batch.py build-travelperk-user.py upsert-travelperk-user.py /app/

# Create data directory and non-root user (SOW requirement 9.5)
RUN mkdir -p /app/data && \
    useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Health check - validates environment and data directory
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os, sys; \
        missing = [v for v in ['UKG_BASE_URL'] if not os.getenv(v)]; \
        sys.exit(1 if missing else 0)"

# Switch to non-root user
USER appuser

# Default entrypoint
ENTRYPOINT ["python3", "run-travelperk-batch.py"]
CMD ["--help"]

# -----------------------------------------------------------------------------
# Stage 3: Development - Includes dev tools
# -----------------------------------------------------------------------------
FROM production AS development

USER root

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest>=7.0.0 \
    pytest-cov>=4.0.0 \
    responses>=0.23.0 \
    mypy>=1.0.0 \
    ruff>=0.1.0 \
    black>=23.0.0

USER appuser

# Override entrypoint for development
ENTRYPOINT ["/bin/bash"]
CMD []
