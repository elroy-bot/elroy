FROM python:3.11.7-slim

RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    python3-dev \
    build-essential \
    git \
    postgresql-client \
    sqlite3 \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy the local package files
COPY . /app

# Install the local package
# Using -e for editable mode so changes to the code are reflected immediately
RUN cd /app && uv pip install --no-cache --system -e ".[dev,tracing]"

ENV ELROY_HOME=/app/data
RUN mkdir -p /app/data && \
    chmod -R 777 /app/data

ENTRYPOINT ["elroy"]
CMD ["chat"]
