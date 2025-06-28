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
RUN pip install --no-cache-dir boto3 uvicorn httpx starlette

# Copy application code
COPY . .

# Create directory for local token storage (fallback)
RUN mkdir -p /app/data

# Expose port
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV TOKEN_STORAGE_PATH=/app/data/slack_tokens.jsonl

# Run the server directly
CMD ["python", "server.py"]