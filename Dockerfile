# Dockerfile for ta-graph trading system
# Using uv for fast dependency management

FROM python:3.13-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib C library (Latest 0.6.4)
RUN wget https://github.com/ta-lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz && \
    tar -xzf ta-lib-0.6.4-src.tar.gz && \
    cd ta-lib-0.6.4/ && \
    ./configure --prefix=/usr && \
    make -j8 && \
    make install && \
    cd .. && \
    rm -rf ta-lib-0.6.4 ta-lib-0.6.4-src.tar.gz

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

# Create trader user first
RUN useradd -m -u 1000 trader

# Create necessary directories and set initial ownership
RUN mkdir -p /app/data /app/logs /app/charts && \
    chown -R trader:trader /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

# Health check - verify database accessibility
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os; os.path.exists('/app/data') or exit(1)"

USER trader

# Run the trading system
CMD ["python", "main.py"]
