FROM python:3.12-slim

WORKDIR /app

# Build context is victros-poc/ (one level up from this Dockerfile)
# Install production dependencies only
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/server/ ./server/
COPY backend/schema/ ./schema/

# Bake git SHA at build time (set by deploy.sh via --build-arg)
ARG BUILD_SHA=unknown
ENV BUILD_SHA=${BUILD_SHA}

EXPOSE 8000

# Production: 2 uvicorn workers. Override CMD for local dev hot-reload.
CMD ["uvicorn", "server.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
