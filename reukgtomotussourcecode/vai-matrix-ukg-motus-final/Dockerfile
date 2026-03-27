FROM python:3.11-slim

# avoid buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# copy code and deps
COPY build-motus-driver.py upsert-motus-driver.py run-motus-batch.py motus-get-token.py /app/
COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

# dir for outputs, logs, etc.
RUN mkdir -p /app/data

# Create non-root user for security (SOW requirement 9.5)
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# by default it exec batch
ENTRYPOINT ["python3", "run-motus-batch.py"]
CMD []
