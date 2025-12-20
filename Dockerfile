FROM python:3.12-slim

# Install uv for fast, reliable package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files first
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-cache

# Copy application code
COPY dashboard.py cloud_intel.py ./
# Copy scripts/ just in case (optional, but good for debug)
COPY scripts/ scripts/

# Create a non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Run the application
# Binds strictly to the PORT env var provided by Cloud Run
CMD ["sh", "-c", "uv run streamlit run dashboard.py --server.port=${PORT} --server.address=0.0.0.0"]
