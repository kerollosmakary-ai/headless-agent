FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Install opencode (if available via npm)
RUN npm install -g @opencode-ai/opencode 2>/dev/null || echo "opencode not on npm, will use binary"

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY app/ ./app/
COPY ../pwa/dist ./static/

EXPOSE 8080

CMD ["python", "-m", "app.main"]
