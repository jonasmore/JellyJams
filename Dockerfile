FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install required packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create directories for playlists, logs, and config
RUN mkdir -p /app/playlists /app/logs /app/config

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV JELLYFIN_URL=http://jellyfin:8096
ENV JELLYFIN_API_KEY=""
ENV PLAYLIST_FOLDER=/app/playlists
ENV LOG_LEVEL=INFO
ENV GENERATION_INTERVAL=24
ENV ENABLE_WEB_UI=true
ENV WEB_PORT=5000

# Expose web UI port
EXPOSE 5000

# Create startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Run the startup script
CMD ["/app/start.sh"]
