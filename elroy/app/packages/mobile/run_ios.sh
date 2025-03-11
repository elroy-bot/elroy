#!/bin/bash

# Start the Elroy Web API in the background
echo "Starting Elroy Web API..."
cd ../../../
elroy web-api run &
API_PID=$!

# Wait for the API to start
echo "Waiting for API to start..."
sleep 5

# Start the Expo development server
echo "Starting Expo development server..."
cd elroy/app/packages/mobile
npx expo start --ios

# When the Expo server is terminated, also terminate the API server
kill $API_PID
