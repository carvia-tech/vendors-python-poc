# Playwright-enabled image, for when the JS-rendering scrape fallback is
# wanted (JS-only / geo-gated sites like prolifics.com). Without it the
# scraper still works - it just skips that retry.
#
# Runs either service; the API is the default, override CMD for the UI:
#   API: uvicorn api.main:app --host 0.0.0.0 --port $PORT
#   UI : streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Dependencies first so image layers cache across code changes.
COPY requirements.txt .ax
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

# Platforms inject $PORT; 8000 is only a local default.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
 