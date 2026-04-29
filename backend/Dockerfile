FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    pkg-config \
    libssl-dev \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# Install TeX Live with pdfLaTeX (matches Overleaf)
RUN apt-get update && apt-get install -y \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-xetex \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model for keyword extraction
RUN python -m spacy download en_core_web_sm || true

# Copy app code
COPY app/ ./app/
COPY templates/ ./templates/

# Create __init__.py if missing
RUN touch app/__init__.py

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
