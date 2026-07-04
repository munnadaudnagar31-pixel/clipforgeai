FROM python:3.10-slim

# Force noninteractive to avoid apt prompts and update mirrors
ENV DEBIAN_FRONTEND=noninteractive

# Install stable system requirements for OpenCV and FFmpeg safely
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Set PYTHONPATH to root so all internal app/ imports work perfectly
ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
