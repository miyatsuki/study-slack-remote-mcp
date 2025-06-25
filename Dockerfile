# Dockerfile for Slack MCP Server
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    openssl \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Install additional AWS dependencies for cloud deployment
RUN pip install --no-cache-dir boto3 uvicorn

# Copy application code
COPY . .

# Create directory for local token storage (fallback)
RUN mkdir -p /app/data

# Expose ports
EXPOSE 8001
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || curl -f http://localhost:8002/health || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV TOKEN_STORAGE_PATH=/app/data/slack_tokens.jsonl

# Run the server
CMD ["python", "server.py"]