# CUDA GPU Backend Setup Guide

## Overview

This document explains how to deploy the KRAI backend with GPU acceleration using CUDA.

## Prerequisites

- NVIDIA GPU with CUDA support (RTX 2000 Ada or better recommended)
- NVIDIA Docker runtime installed
- Docker Compose

## Files

### Dockerfile.cuda310
- **Purpose**: Production Dockerfile with CUDA 12.0 and Python 3.10
- **Base Image**: `nvidia/cuda:12.0.1-base-ubuntu20.04`
- **Python Version**: 3.10 (required for colpali-engine)
- **GPU Support**: Full CUDA acceleration for PyTorch and compatible models

### docker-compose.cuda.yml
- **Purpose**: Docker Compose configuration for GPU deployment
- **GPU Reservation**: Uses `device_ids: ['0']` for GPU access
- **Services**: krai-engine-cuda, krai-postgres-prod, krai-redis-prod, krai-ollama

## Usage

### Build and Run with GPU
```bash
# Build CUDA image
docker build -f Dockerfile.cuda310 -t krai-engine-cuda .

# Run with GPU support
docker-compose -f docker-compose.cuda.yml up -d
```

### Verify GPU Support
```bash
# Check GPU detection
docker exec krai-engine-cuda nvidia-smi

# Verify PyTorch CUDA
docker exec krai-engine-cuda python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

## GPU Models Available

When running with CUDA support, the following models are GPU-accelerated:
- **LLaMA 3.2**: Latest language model
- **nomic-embed-text**: Text embedding model
- **llava**: Vision-language model

## Performance Benefits

- **Text Processing**: 3-5x faster with GPU
- **Embeddings**: 10x faster for large batches
- **Vision Models**: Real-time processing possible
- **Memory**: 8GB VRAM supports larger models

## Troubleshooting

### GPU Not Detected
```bash
# Check NVIDIA Docker runtime
docker run --rm --gpus all nvidia/cuda:12.0.1-base-ubuntu20.04 nvidia-smi
```

### Out of Memory
Reduce batch sizes or use smaller models. Monitor with:
```bash
docker exec krai-engine-cuda nvidia-smi -l 1
```

### CUDA Version Mismatch
Ensure host CUDA driver version matches container (12.0+ recommended).

## Migration from CPU

To migrate from CPU to GPU deployment:
1. Stop existing services: `docker-compose down`
2. Backup data if needed
3. Start GPU services: `docker-compose -f docker-compose.cuda.yml up -d`
4. Verify GPU functionality as shown above

## Environment Variables

Key variables for GPU deployment:
- `CUDA_VISIBLE_DEVICES`: Control which GPUs are visible
- `TORCH_CUDA_ARCH_LIST`: Specify GPU architectures (auto-detected)
- `OLLAMA_GPU`: Set to `1` to enable Ollama GPU acceleration
