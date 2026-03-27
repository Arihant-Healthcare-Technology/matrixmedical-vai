FROM python:3.11-slim

# avoid buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# copy common module (self-contained)
COPY common/ /app/common/

# copy main application files
COPY build-bill-entity.py upsert-bill-entity.py run-bill-batch.py /app/
COPY build-bill-invoice.py upsert-bill-invoice.py /app/
COPY build-bill-vendor.py upsert-bill-vendor.py /app/
COPY process-bill-payment.py run-ap-batch.py /app/
COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

# dir for outputs, logs, etc.
RUN mkdir -p /app/data/batch

# Create non-root user for security (SOW requirement 9.5)
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# by default it exec batch
ENTRYPOINT ["python3", "run-bill-batch.py"]
CMD []
