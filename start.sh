#!/bin/bash

# JellyJams Container Startup Script

echo "🎵 Starting JellyJams Generator..."

# Set log level to DEBUG for comprehensive logging
export LOG_LEVEL=DEBUG

# Function to run playlist generator in background
run_generator() {
    echo "🎯 Starting playlist generator background process..."
    python vibecodeplugin.py &
    GENERATOR_PID=$!
    echo "📊 Playlist generator started with PID: $GENERATOR_PID"
}

# Check if web UI is enabled
if [ "$ENABLE_WEB_UI" = "true" ]; then
    echo "🌐 Web UI enabled - starting both web UI and playlist generator"
    
    # Start playlist generator in background
    run_generator
    
    # Start the web application with Gunicorn (with logging to stdout)
    echo "🌐 Starting web UI on port $WEB_PORT"
    exec gunicorn --bind 0.0.0.0:$WEB_PORT --workers 2 --timeout 120 --access-logfile - --error-logfile - webapp:app
else
    echo "🎯 Web UI disabled - running playlist generator only"
    
    # Run the original playlist generator
    exec python vibecodeplugin.py
fi
