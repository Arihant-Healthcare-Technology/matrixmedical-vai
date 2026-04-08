# =============================================================================
# UKG-BILL Integration Dockerfile
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
LABEL org.opencontainers.image.title="UKG-BILL Integration"
LABEL org.opencontainers.image.description="UKG Pro to BILL.com User and AP Sync Service"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.vendor="VAI Consulting"
LABEL org.opencontainers.image.source="https://github.com/vai-consulting/vai-matrix-ukg-bill"
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

# Copy application code (Clean Architecture)
COPY src/ /app/src/
COPY common/ /app/common/

# Copy legacy scripts (deprecated but still needed for backward compatibility)
COPY build-bill-entity.py upsert-bill-entity.py run-bill-batch.py /app/
COPY build-bill-invoice.py upsert-bill-invoice.py /app/
COPY build-bill-vendor.py upsert-bill-vendor.py /app/
COPY process-bill-payment.py run-ap-batch.py /app/
COPY orchestrate_people_import.py /app/

# Create data directories and non-root user (SOW requirement 9.5)
RUN mkdir -p /app/data/batch /app/data/reports && \
    useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Health check - validates environment and data directory
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os, sys; \
        missing = [v for v in ['UKG_BASE_URL', 'BILL_API_BASE'] if not os.getenv(v)]; \
        sys.exit(1 if missing else 0)"

# Switch to non-root user
USER appuser

# Default entrypoint - uses new CLI
ENTRYPOINT ["python3", "-m", "src.presentation.cli.main"]
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

# -----------------------------------------------------------------------------
# Stage 4: Scraping - Includes Playwright for UI automation (Azure-compatible)
# -----------------------------------------------------------------------------
# NOTE: This stage is OPTIONAL. Only build if you need web UI automation.
# For API-based sync, use the 'production' stage instead.
#
# Build with: docker build --target scraping -t vai-ukg-bill:scraping .
# -----------------------------------------------------------------------------
FROM production AS scraping

USER root

# Set Playwright environment variables BEFORE installation
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
ENV PLAYWRIGHT_SKIP_BROWSER_GC=1

# Install ALL required system dependencies for Playwright Chromium
# Reference: https://playwright.dev/python/docs/browsers#install-system-dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core browser dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    # Additional dependencies often missing
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxi6 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    # Fonts (required for proper rendering)
    fonts-liberation \
    fonts-noto-color-emoji \
    # CA certificates for HTTPS
    ca-certificates \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create browser directory with proper permissions
RUN mkdir -p ${PLAYWRIGHT_BROWSERS_PATH} && \
    chmod 777 ${PLAYWRIGHT_BROWSERS_PATH}

# Install Playwright and download Chromium browser
RUN pip install --no-cache-dir playwright==1.40.0 && \
    playwright install chromium --with-deps || playwright install chromium

# Set proper permissions on browser directory for non-root user
RUN chmod -R 755 ${PLAYWRIGHT_BROWSERS_PATH} && \
    chown -R appuser:appuser ${PLAYWRIGHT_BROWSERS_PATH}

# Copy scraping module
COPY scraping/ /app/scraping/

# Create screenshots directory with proper permissions
RUN mkdir -p /app/scraping/screenshots && \
    chown -R appuser:appuser /app/scraping && \
    chmod -R 755 /app/scraping

USER appuser

# Verify Playwright installation
RUN python -c "from playwright.sync_api import sync_playwright; print('Playwright installed successfully')"

ENTRYPOINT ["python3", "orchestrate_people_import.py"]
CMD ["--help"]
