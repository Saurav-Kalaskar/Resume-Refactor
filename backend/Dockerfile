FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    pkg-config \
    libssl-dev \
    libfontconfig1 \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-xetex \
    && rm -rf /var/lib/apt/lists/*

# Set working directory inside container
WORKDIR /app

# Copy requirements from backend folder (build context is repo root)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm || true

# Copy application code from backend folder
COPY backend/app/ ./app/
COPY backend/templates/ ./templates/

# Copy resume.tex from repo root
COPY resume.tex ./resume.tex

# Ensure __init__.py exists
RUN touch app/__init__.py

# Set environment variable for default resume path
ENV DEFAULT_RESUME_PATH=/app/resume.tex

EXPOSE 8000

# Run FastAPI application with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
