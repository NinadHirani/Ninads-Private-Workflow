FROM python:3.11-slim

# Install FFmpeg and basic utilities
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    git \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY docker/python/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

CMD ["python3", "-m", "pytest", "tests/"]
