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

# Create logs directory (mounted in compose as a volume)
RUN mkdir -p /app/logs

ENV API_PORT=8100
EXPOSE $API_PORT

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${API_PORT}"]


