FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*

# Non-root user; /data holds the uploaded originals (a volume in docker-compose).
RUN useradd --create-home --uid 1000 app && mkdir -p /data/uploads && chown -R app:app /data
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# MiniLM sentence-embedding model (about 90 MB, every file hash-checked by the script) baked into the image,
# so semantic matching uses real embeddings and not the TF-IDF fallback. The script writes to <root>/backend/storage/models.
COPY scripts/fetch_minilm.py /build/scripts/fetch_minilm.py
RUN python /build/scripts/fetch_minilm.py \
    && mkdir -p /app/storage && mv /build/backend/storage/models /app/storage/models && rm -rf /build

COPY backend/ /app/
RUN chown -R app:app /app
USER app

ENV UPLOAD_DIR=/data/uploads EMBEDDING_BACKEND=auto
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/docs', timeout=4).status == 200 else 1)"
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
