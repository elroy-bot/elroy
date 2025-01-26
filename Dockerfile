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


ARG ELROY_VERSION

RUN if [ -z "$ELROY_VERSION" ] ; then \
        uv pip install --no-cache --system elroy ; \
    else \
        uv pip install --no-cache --system elroy==${ELROY_VERSION} ; \
    fi

ENV ELROY_HOME=/app/data
RUN mkdir -p /app/data && \
    chmod -R 777 /app/data

ENTRYPOINT ["elroy"]
CMD ["chat"]
