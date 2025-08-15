#!/bin/bash

# Default values
SPEED=2
OUTPUT_NAME="demo"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--speed)
            SPEED="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_NAME="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -s, --speed SPEED     Playback speed multiplier (default: 2)"
            echo "  -o, --output NAME     Output filename without extension (default: demo)"
            echo "  -h, --help           Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Check if required tools are installed
if ! command -v asciinema &> /dev/null; then
    echo "Error: asciinema is not installed. Install with: pip install asciinema or brew install asciinema"
    exit 1
fi

if ! command -v agg &> /dev/null; then
    echo "Error: agg is not installed. Install with: cargo install --git https://github.com/asciinema/agg, or brew install agg"
    exit 1
fi

echo "🎬 Starting demo recording..."
echo "📝 Output will be: ${OUTPUT_NAME}.gif"
echo "⚡ Speed: ${SPEED}x"
echo ""

echo ""
echo "🔴 Recording will start in 3 seconds..."
echo "   Type 'exit' or press Ctrl+D to stop recording"
sleep 3

# Start recording with temporary profile
asciinema rec --overwrite "${OUTPUT_NAME}.cast"

# Convert to GIF with specified speed
echo ""
echo "🎞️  Converting to GIF at ${SPEED}x speed..."
agg --speed "${SPEED}" "${OUTPUT_NAME}.cast" "${OUTPUT_NAME}.gif"


# Clean up temporary files
rm "${OUTPUT_NAME}.cast"

echo ""
echo "✅ Demo recording complete!"
echo "📁 Output: ${OUTPUT_NAME}.gif"
