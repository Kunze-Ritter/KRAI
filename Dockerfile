# Production Dockerfile for KRAI Engine with CUDA Support
# Security: No secrets are baked into this image
# All configuration is provided at runtime via environment variables

FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

# Set environment variables for CUDA
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=$PATH:$CUDA_HOME/bin
ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CUDA_HOME/lib64

# Set working directory
WORKDIR /app

# Set non-interactive environment first
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    curl \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng \
    libpq-dev \
    gcc \
    pkg-config \
    libcairo2-dev \
    libfreetype6-dev \
    libfontconfig1-dev \
    libmagic1 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set timezone after installation
RUN ln -fs /usr/share/zoneinfo/Europe/Berlin /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata

# Create symlink for python
RUN ln -s /usr/bin/python3.11 /usr/bin/python

# Upgrade pip
RUN python -m pip install --upgrade pip

# Copy requirements + lock
COPY backend/requirements.txt backend/constraints.txt ./

# Install Python dependencies with CUDA support
# Note: torch will be installed with CUDA support via index-url
# constraints.txt pins the full resolved tree for reproducible builds (excludes
# torch/torchvision/nvidia-*, which are the CUDA wheels installed below).
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt gunicorn \
    --index-url https://download.pytorch.org/whl/cu124 \
    --extra-index-url https://pypi.org/simple

# Install PyTorch with CUDA support separately to ensure correct version
RUN pip install --no-cache-dir torch==2.11.0 torchvision==0.26.0 \
    --index-url https://download.pytorch.org/whl/cu124

# Set PYTHONPATH to project root; all imports use the 'backend.' package prefix.
# Placed after pip so dependency layers stay cached when only code changes.
ENV PYTHONPATH=/app:${PYTHONPATH}

# Copy application code to /app/backend/
COPY backend/ /app/backend/
COPY scripts/ /app/scripts/

# Switch to backend directory for all subsequent commands
WORKDIR /app/backend

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/temp

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command (can be overridden)
CMD ["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
