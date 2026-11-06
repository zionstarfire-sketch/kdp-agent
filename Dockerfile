FROM python:3.12-slim

# Install system dependencies and Chromium for headless print-to-PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    fonts-dejavu-core \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package resolution and virtualenv management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy dependency definition files
COPY pyproject.toml uv.lock ./

# Install pinned dependencies
RUN uv sync --frozen --no-install-project

# Copy application source code
COPY . .

# Environment settings
ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV BROWSER_PATH=/usr/bin/chromium

EXPOSE 7860

# Launch Gradio dashboard
CMD ["uv", "run", "python", "-u", "main.py"]
