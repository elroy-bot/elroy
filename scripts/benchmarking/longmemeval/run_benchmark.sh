#!/bin/bash

# Set default values
RUN_ID=${1:-run_$(date +%s)}
DATA_FILE=${2:-data/longmemeval_s.json}

echo "Starting benchmark with run ID: $RUN_ID and data file: $DATA_FILE"

# Check if data directory exists
if [ ! -d "data" ]; then
  echo "Data directory not found. Creating..."
  mkdir -p data
  echo "Please download the benchmark data and place it in the data directory."
  echo "Download link: https://drive.google.com/file/d/1zJgtYRFhOh5zDQzzatiddfjYhFSnyQ80/view"
  exit 1
fi

# Check if the data file exists
if [ ! -f "$DATA_FILE" ]; then
  echo "Data file not found: $DATA_FILE"
  echo "Please download the benchmark data and place it in the data directory."
  echo "Download link: https://drive.google.com/file/d/1zJgtYRFhOh5zDQzzatiddfjYhFSnyQ80/view"
  exit 1
fi

# Start the services
docker-compose up -d postgres redis litellm

# Wait for postgres to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 10

# Run the benchmark
docker-compose run --rm benchmark python scripts/benchmarking/longmemeval/run.py "$DATA_FILE" "$RUN_ID"

echo "Benchmark completed with run ID: $RUN_ID"
echo "Results are stored in the PostgreSQL database."
