# ==============================================================================
# RepoPilot AI Backend — Production Dockerfile
# ==============================================================================
# Multi-layer Dockerfile for FastAPI backend:
# - Official Python 3.12 slim base (Debian Bookworm glibc compatibility for PyTorch)
# - Non-root execution user for defense-in-depth security
# - Layered dependency caching for fast iterative builds
# - Dynamic $PORT support with 0.0.0.0 host binding
# ==============================================================================

FROM python:3.12-slim-bookworm

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOME=/home/repopilot \
    HF_HOME=/home/repopilot/.cache/huggingface \
    TORCH_HOME=/home/repopilot/.cache/torch

# Create a dedicated non-root user and group with home directory
RUN groupadd -g 10001 repopilot && \
    useradd -u 10001 -g repopilot -d /home/repopilot -m -s /bin/bash repopilot

# Set the working directory
WORKDIR /app

# Upgrade pip and install Python dependencies before copying source code
# (Leverages Docker build cache so code edits don't trigger re-installation)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code with proper ownership
COPY --chown=repopilot:repopilot . /app

# Ensure non-root user owns the working directory and home cache directory
RUN chown -R repopilot:repopilot /app /home/repopilot

# Switch to non-root user
USER repopilot

# Expose backend port
EXPOSE 8000

# Built-in container health check using Python standard library (no curl required)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request, os; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health')" || exit 1

# Production startup command: runs Uvicorn bound to 0.0.0.0 with dynamic $PORT support
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
