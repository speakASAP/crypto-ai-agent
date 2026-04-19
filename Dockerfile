FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/app /app/app
RUN [ -d backend/templates ] && cp -r backend/templates /app/templates || echo "No templates found"

RUN mkdir -p /app/logs

ENV API_PORT=3000
EXPOSE $API_PORT

CMD ["sh", "-c", "gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${API_PORT} --timeout 90 --access-logfile - --error-logfile -"]
