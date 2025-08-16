#!/bin/bash

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for Homebrew
if ! command_exists brew; then
    echo "Homebrew is not installed. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Check for required tools
if ! command_exists ffmpeg; then
    echo "FFmpeg is not installed. Installing via Homebrew..."
    brew install ffmpeg
fi

if ! command_exists gifsicle; then
    echo "Gifsicle is not installed. Installing via Homebrew..."
    brew install gifsicle
fi

# Check if input file was provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <input_mp4_file> [output_gif_file]"
    exit 1
fi

INPUT_FILE="$1"

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file '$INPUT_FILE' does not exist"
    exit 1
fi

# If no output file specified, create one based on input filename
if [ -z "$2" ]; then
    OUTPUT_FILE="${INPUT_FILE%.*}.gif"
else
    OUTPUT_FILE="$2"
fi

echo "Converting $INPUT_FILE to GIF..."

# Create temporary file for initial conversion
TEMP_GIF="${OUTPUT_FILE}.temp.gif"

# Convert to GIF with higher quality settings for GitHub
# - fps=15 for smoother animation
# - scale=1440:-1 for high resolution while maintaining aspect ratio
# Using palettegen and paletteuse for better color quality
ffmpeg -i "$INPUT_FILE" \
    -vf "fps=15,scale=1440:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
    -loop 0 \
    "$TEMP_GIF"

# Optimize the GIF using gifsicle with less aggressive compression
echo "Optimizing GIF..."
gifsicle -O3 --lossy=20 "$TEMP_GIF" -o "$OUTPUT_FILE"

# Remove temporary file
rm "$TEMP_GIF"

if [ $? -eq 0 ]; then
    echo "Conversion complete! GIF saved as: $OUTPUT_FILE"
    
    # Print file sizes for comparison
    MP4_SIZE=$(du -h "$INPUT_FILE" | cut -f1)
    GIF_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo "MP4 size: $MP4_SIZE"
    echo "GIF size: $GIF_SIZE"
else
    echo "Error: Conversion failed"
    exit 1
fi
