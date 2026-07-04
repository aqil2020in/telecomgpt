FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV APP_ENV=production
ENV TNIC_ENABLE_CHROMA=0
ENV TNIC_DATASETS_DIR=/app/data/datasets

EXPOSE 8000

CMD ["sh", "-c", "uvicorn tnic.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
