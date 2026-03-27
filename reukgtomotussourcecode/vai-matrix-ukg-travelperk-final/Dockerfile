FROM python:3.11-slim

# avoid buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# copy code and deps
COPY build-travelperk-user.py upsert-travelperk-user.py run-travelperk-batch.py /app/
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
ENTRYPOINT ["python3", "run-travelperk-batch.py"]
CMD []