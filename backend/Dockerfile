FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (curl for healthchecks, build essentials if needed later)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY app /app/app

# Copy templates directory for CSV import
COPY templates /app/templates

# Create logs directory (mounted in compose as a volume)
RUN mkdir -p /app/logs

ENV API_PORT=8100
EXPOSE $API_PORT

# Start application with Gunicorn (production-ready ASGI server)
# Default to one worker to keep the pod inside its memory limit; override with GUNICORN_WORKERS.
CMD ["sh", "-c", "gunicorn app.main:app --workers ${GUNICORN_WORKERS:-1} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${API_PORT} --timeout 90 --access-logfile - --error-logfile -"]


