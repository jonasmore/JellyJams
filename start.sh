#!/bin/bash

# JellyJams Container Startup Script

echo "🎵 Starting JellyJams Generator..."

# Check if web UI is enabled
if [ "$ENABLE_WEB_UI" = "true" ]; then
    echo "🌐 Web UI enabled - starting Flask application on port $WEB_PORT"
    
    # Start the web application with Gunicorn
    exec gunicorn --bind 0.0.0.0:$WEB_PORT --workers 2 --timeout 120 webapp:app
else
    echo "🎯 Web UI disabled - running playlist generator only"
    
    # Run the original playlist generator
    exec python vibecodeplugin.py
fi
