FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
# torch is a transitive dependency of sentence-transformers, and the default
# PyPI wheel bundles full CUDA support — several GB of NVIDIA packages
# (cudnn, cusparselt, nccl, ...) this CPU-only service never uses. Installing
# the CPU-only build first, from PyTorch's own CPU index, satisfies
# sentence-transformers' requirement without pip ever reaching for the GPU
# variant — found by timing an actual local build, which spent most of its
# time downloading GPU libraries with no code path that calls them.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
