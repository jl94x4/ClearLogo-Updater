# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set metadata
LABEL maintainer="P Logo Updater"
LABEL description="Automatically update Plex logos from Fanart.tv"

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY *.py ./
COPY tests/ ./tests/

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Create volume mount points
VOLUME ["/app/config", "/app/data"]

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command (can be overridden by docker-compose)
ENTRYPOINT ["python", "clearlogo.py"]
CMD ["--help"]
