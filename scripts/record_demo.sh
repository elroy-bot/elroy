#!/bin/bash

# best screen size: Rows: 27, Columns: 118


# Define the output file name
OUTPUT_FILE="terminal_recording_$(date +'%Y-%m-%d_%H-%M-%S').mov"

echo "Starting screen recording..."
echo "Press Command + Control + Esc to stop recording"

# Use macOS native screen recording
screencapture -v "$OUTPUT_FILE"

echo "Recording saved as $OUTPUT_FILE"
