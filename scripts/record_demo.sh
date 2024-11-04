#!/bin/bash

# best screen size: Rows: 27, Columns: 118

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for Homebrew
if ! command_exists brew; then
    echo "Homebrew is not installed. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Check for FFmpeg
if ! command_exists ffmpeg; then
    echo "FFmpeg is not installed. Installing via Homebrew..."
    brew install ffmpeg
fi

# Define the output video file name
OUTPUT_FILE="terminal_recording_$(date +'%Y-%m-%d_%H-%M-%S').mp4"

echo "Starting screen recording..."
echo "Press Control + C to stop recording"

# On macOS, screen capture is typically device 1
SCREEN_NUM="1"

echo "Starting recording of main display..."
ffmpeg -f avfoundation -i "$SCREEN_NUM:none" \
    -framerate 30 \
    -pix_fmt uyvy422 \
    -capture_cursor 1 \
    -capture_mouse_clicks 1 \
    -c:v libx264 \
    -preset ultrafast \
    -r 30 \
    "$OUTPUT_FILE"

echo "Recording saved as $OUTPUT_FILE"
