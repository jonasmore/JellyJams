#!/usr/bin/env sh
set -eu

: "${PUID:=0}"
: "${PGID:=0}"
: "${UMASK:=022}"

# Validate numeric PUID/PGID (digits only)
case "$PUID" in (*[!0-9]*) echo "ERROR: PUID must be numeric (got '$PUID')" >&2; exit 64;; esac
case "$PGID" in (*[!0-9]*) echo "ERROR: PGID must be numeric (got '$PGID')" >&2; exit 64;; esac

# Apply umask for the process tree
umask "$UMASK" || true

# Create app-data directories
mkdir -p /data /data/config /data/logs

# Put default cover art in /data if not already there
if [ ! -d "/data/cover" ]; then
    echo "Moving default cover art to /data/cover"
    cp -r /app/cover /data/
fi

if [ "$PUID" != "0" ] || [ "$PGID" != "0" ]; then
    
    # Fix ownership
    WRITABLE_DIRS="/app /data /playlists"
    for d in $WRITABLE_DIRS; do
        [ -d "$d" ] && chown -R "$PUID:$PGID" "$d" 2>/dev/null || true
    done
    
    # Start the app with the specified UID and GID
    exec su-exec "$PUID:$PGID" /app/start.sh
    
else

    # Start the app as root
    exec /app/start.sh

fi
