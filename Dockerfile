# Dockerfile for ta-graph trading system
# Using uv for fast dependency management

FROM python:3.13-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# ========================================
# Stage 2: Install dependencies
# ========================================
FROM base as dependencies

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Sync dependencies using uv (much faster than pip)
RUN uv sync --frozen --no-dev

# ========================================
# Stage 3: Application
# ========================================
FROM base as application

# Copy installed dependencies from previous stage
COPY --from=dependencies /app/.venv /app/.venv

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/charts

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

# Health check - verify database accessibility
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os; os.path.exists('/app/data') or exit(1)"

# Run as non-root user for security
RUN useradd -m -u 1000 trader && \
    chown -R trader:trader /app
USER trader

# Run the trading system
CMD ["python", "main.py"]
