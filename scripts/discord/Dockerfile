FROM python:3.11.7-slim

RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    python3-dev \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Clone elroy repository
RUN git clone https://github.com/elroy-bot/elroy.git /app/elroy-src

# Install elroy from source and other dependencies
RUN cd /app/elroy-src && uv pip install --system -e .
RUN uv pip install --system discord.py

# Copy just the discord bot script
COPY scripts/discord/bot.py /app/scripts/

ENV ELROY_HOME=/app/data
RUN mkdir -p /app/data && \
    chmod -R 777 /app/data

CMD ["python", "scripts/bot.py"]
