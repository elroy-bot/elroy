FROM python:3.11.7-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    python3-dev \
    build-essential \
    git \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install specific elroy version
ARG ELROY_VERSION
RUN if [ -z "$ELROY_VERSION" ] ; then \
        pip install --no-cache-dir elroy ; \
    else \
        pip install --no-cache-dir elroy==${ELROY_VERSION} ; \
    fi

# Set the PYTHONPATH
ENV PYTHONPATH=/app
