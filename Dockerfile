FROM python:3.11-slim-bookworm

# Force noninteractive to avoid apt prompts
ENV DEBIAN_FRONTEND=noninteractive

# Use a more robust apt-get sequence and clean up properly
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
    curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Set PYTHONPATH to root so all internal app/ imports work perfectly
ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
