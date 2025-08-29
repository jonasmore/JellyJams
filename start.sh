#!/usr/bin/env sh

# JellyJams Container Startup Script

echo "🎵 Starting JellyJams Generator..."

# Initialize default cover files if they don't exist
echo "🖼️ Checking for default cover files..."
if [ -d "/app/default_cover" ] && [ "$(ls -A /app/default_cover 2>/dev/null)" ]; then
    for file in /app/default_cover/*; do
        filename=$(basename "$file")
        if [ ! -f "/app/cover/$filename" ]; then
            echo "📁 Copying default cover: $filename"
            cp "$file" "/app/cover/"
        else
            echo "✅ Custom cover exists, skipping: $filename"
        fi
    done
    echo "🎨 Cover file initialization complete"
else
    echo "⚠️ No default cover files found in /app/default_cover"
fi

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
    echo "🌐 Starting web UI on port 5000"
    exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 --access-logfile - --error-logfile - webapp:app
else
    echo "🎯 Web UI disabled - running playlist generator only"
    
    # Run the original playlist generator
    exec python vibecodeplugin.py
fi
