ARG BASE_IMAGE=celery-crawl-hub:base
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="celery-crawl-hub" \
      org.opencontainers.image.description="Configurable crawler task hub powered by FastAPI, Celery and Playwright"

WORKDIR /workspace

# Base image already includes system deps, Python deps and the Playwright
# browser. This stage only copies the project source, so rebuilds are fast.
COPY . .

EXPOSE 8000 7860

CMD ["python", "main.py"]
