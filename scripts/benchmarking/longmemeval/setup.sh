#!/bin/bash
set -e

# Define paths
DATA_DIR="data"
TARBALL="${DATA_DIR}/longmemeval_data.tar.gz"
EXTRACTED_DIR="${DATA_DIR}/longmemeval_data"

# Create data directory if it doesn't exist
mkdir -p "${DATA_DIR}"

# Check if either the tarball or extracted directory exists
if [ ! -f "${TARBALL}" ] && [ ! -d "${EXTRACTED_DIR}" ]; then
    echo "Error: Neither ${TARBALL} nor ${EXTRACTED_DIR} exists."
    echo "Please download the LongMemEval dataset first."
    exit 1
fi

# If only the tarball exists, extract it
if [ -f "${TARBALL}" ] && [ ! -d "${EXTRACTED_DIR}" ]; then
    echo "Extracting ${TARBALL}..."
    mkdir -p "${EXTRACTED_DIR}"
    tar -xzf "${TARBALL}" -C "${DATA_DIR}"
    echo "Extraction complete."
fi

echo "LongMemEval dataset is ready."
