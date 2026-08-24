# Multi-stage / lightweight Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install system dependencies (ffmpeg is essential for audio conversions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application files
COPY api.py cloud_pipeline.py /app/
COPY core /app/core/

# Create runtime directories
RUN mkdir -p /app/inputs /app/outputs /app/sessions

# Expose default port
EXPOSE 8000

# Start FastAPI server using shell expansion for PORT
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
