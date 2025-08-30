#!/usr/bin/env sh

# JellyJams Container Startup Script

echo "🎵 Starting JellyJams Generator..."

# Create app-data directories
mkdir -p /data /data/config /data/logs

# Put default cover art in /data if not already there
if [ ! -d "/data/cover" ]; then
    echo "Moving default cover art to /data/cover"
    cp -r /app/cover /data/
fi

# Set log level to DEBUG for comprehensive logging
export LOG_LEVEL=DEBUG

# Function to run playlist generator in background
run_generator() {
    echo "🎯 Starting playlist generator background process..."
    python /app/vibecodeplugin.py &
    GENERATOR_PID=$!
    echo "📊 Playlist generator started with PID: $GENERATOR_PID"
}

# Check if web UI is enabled
if [ "$ENABLE_WEB_UI" = "true" ]; then
    echo "🌐 Web UI enabled - starting both web UI and playlist generator"
    
    # Start playlist generator in background
    run_generator
    
    # Start the web application with Gunicorn (with logging to stdout)
    echo "🌐 Starting web UI on port 5000"
    exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 --access-logfile - --error-logfile - webapp:app
else
    echo "🎯 Web UI disabled - running playlist generator only"
    
    # Run the original playlist generator
    exec python /app/vibecodeplugin.py
fi
