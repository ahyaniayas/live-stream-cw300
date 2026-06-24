FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3.10 python3-pip \
    libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libgl1-mesa-glx ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# PyTorch CUDA dulu agar ultralytics tidak install versi CPU-only
RUN pip3 install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu118
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3001
CMD ["python3", "app.py"]
