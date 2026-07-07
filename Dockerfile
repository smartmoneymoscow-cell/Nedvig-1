FROM python:3.11-slim

WORKDIR /app

# Use lightweight requirements for Render free tier
COPY backend/requirements.render.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Remove .env if accidentally copied (Render uses env vars)
RUN rm -f .env

# Render sets PORT dynamically
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
