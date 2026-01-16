# Build stage
FROM python:3.9-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.9-slim

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    libmagic1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY static/ ./static/
# Alembic migrations
COPY alembic.ini ./alembic.ini
COPY alembic/ ./alembic/
COPY scripts/backend_entrypoint.sh ./scripts/backend_entrypoint.sh
# COPY manage/ ./manage/
# COPY .env . # .env will be mounted or copied by deploy script

# Create empty db file if not exists (will be overwritten by volume if mounted)
RUN touch healthy.db

# Expose port
EXPOSE 8000

# Command
RUN chmod +x /app/scripts/backend_entrypoint.sh
CMD ["/app/scripts/backend_entrypoint.sh"]

