# Stage 1: Build Stage
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Production Security-Hardened Runner
FROM python:3.11-slim AS runner

WORKDIR /app
COPY --from=builder /install /usr/local
COPY . /app

# Create non-root user for security compliance
RUN groupadd -r appgroup && useradd -r -g appgroup appuser \
    && mkdir -p /data && chown -R appuser:appgroup /app /data

USER appuser

EXPOSE 5200

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5200/health')" || exit 1

CMD ["python", "analyzer.py"]
