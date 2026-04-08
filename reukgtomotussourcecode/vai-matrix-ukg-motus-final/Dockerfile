FROM python:3.11-slim

# avoid buffering stdout/stderr
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# copy application code from src folder
COPY src/ /app/src/
COPY common/ /app/common/
COPY motus-get-token.py /app/
COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

# dir for outputs, logs, etc.
RUN mkdir -p /app/data

# Create non-root user for security (SOW requirement 9.5)
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Use src-based batch runner as entry point
ENTRYPOINT ["python3", "-m", "src.presentation.cli.batch_runner"]
CMD []
