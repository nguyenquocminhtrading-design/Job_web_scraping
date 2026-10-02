FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright, etc.
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps

COPY . .

# Default command can be overridden in docker-compose.yml
CMD ["uvicorn", "layer5_output.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
