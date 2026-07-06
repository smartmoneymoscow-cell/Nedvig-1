FROM python:3.11-slim

WORKDIR /app

# Use lightweight requirements for Render free tier
COPY requirements.render.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render sets PORT dynamically
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
