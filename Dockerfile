# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Provide a sensible default for the SEC user agent; override in production
ENV COMMONIZE_USER_AGENT="CommonizeApp/0.1 (contact@example.com)"

# Expose the FastAPI web server port
EXPOSE 8000

# Default command runs the web app via uvicorn
CMD ["uvicorn", "commonize.web:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
