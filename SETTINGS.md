# JellyJams Configuration Guide

This document provides comprehensive documentation for all JellyJams configuration options.

## 📋 Table of Contents

- [Configuration Methods](#configuration-methods)
- [Essential Settings](#essential-settings)
- [Playlist Generation Settings](#playlist-generation-settings)
- [Personalized Playlist Settings](#personalized-playlist-settings)
- [Discovery Playlist Settings](#discovery-playlist-settings)
- [Cover Art Settings](#cover-art-settings)
- [Spotify Integration Settings](#spotify-integration-settings)
- [System Settings](#system-settings)
- [Web UI Settings](#web-ui-settings)
- [Docker Volume Configuration](#docker-volume-configuration)
- [Examples](#examples)

## 🐳 Docker Hub

**Official Docker Image**: [jonasmore/jellyjams](https://hub.docker.com/r/jonasmore/jellyjams)

```bash
docker pull jonasmore/jellyjams:latest
```

## 🔧 Configuration Methods

JellyJams supports two configuration methods:

### 1. Environment Variables
Most app settings are now configurable only in the web UI. Some settings can only be set in your `.env` for now.

### 2. Web UI Settings
Enter settings at `http://localhost:{WEB_PORT}/settings`. These settings are persistent and take precedence.

## 🎯 Essential Settings

### Jellyfin Integration
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `JELLYFIN_URL` | Your Jellyfin server URL | ✅ Yes | http://jellyfin:8096 |
| `JELLYFIN_API_KEY` | Jellyfin API key with media access | ✅ Yes | - |
| `PLAYLIST_DIR_HOST` | Path to Jellyfin playlists on host | ✅ Yes | `./jellyfin/config/data/playlists` |
| `MUSIC_DIR_HOST` | Path to music on host | No | - |
| `MUSIC_DIR_CONTAINER` | Path to music in Jellyfin container | No | - |
| `TRIGGER_LIBRARY_SCAN` | Jellyfin scans library after playlist generation | No | `true` |
| `PUID` | Process/User ID for Jellyfin and JellyJams | No | `1000`
| `PUID` | Process/Group ID for Jellyfin and JellyJams | No | `1000`

**Example:**
```bash
JELLYFIN_URL=http://jellyfin:8096
JELLYFIN_API_KEY=your_32_character_api_key_here
PLAYLIST_DIR_HOST=/mnt/user/appdata/jellyfin/data/playlists
MUSIC_DIR_HOST=/mnt/user/media/data/music
MUSIC_DIR_CONTAINER=/mnt/user/media/data/music
# Trigger Jellyfin media library scan after playlist creation (default: true)
TRIGGER_LIBRARY_SCAN=true
# User and group ID that Jellyfin runs with
PUID=1000
PGID=1000
```
**Notes:**
- `JELLYJAMS_DATA_DIR_HOST` - Create this directory before starting the container.
- `PLAYLIST_DIR_HOST` - JellyJams needs direct R/W access to Jellyfin's playlists directory.
- `MUSIC_DIR_HOST` - Read-only access to your Jellyfin music library is needed if you want JellyJams to pull artwork from there.
- `MUSIC_DIR_CONTAINER` - The music needs to be mapped to the same directory in the container as it is in Jellyfin. This is because JellyJams gets the path of music sub-directories from the Jellyfin API, which provides the path as it is in the Jellyfin container.

**User / Group Identifiers:**
Permissions issues can arise between the host OS and the container, we avoid this issue by allowing you to specify the user PUID and group PGID.

Ensure any volume directories on the host are owned by the same user you specify and any permissions issues will vanish. Jellyfin and JellyJams need to use the same PUID and PGUI, because they both write to the playlists directory.

Commonly on the host, PUID=1000 and PGID=1000. To find yours use `id your_user` as below:
```bash
id your_user
# Example output:
# uid=1000(your_user) gid=1000(your_user) groups=1000(your_user)
```

If your Jellyfin container doesn't use PUID/GUID or the Docker Compose `user: "$PUID:PGID"` setting, it is likely running as root. In that case, you can omit the PUID and GUID settings from both containers, or set them to `0` for JellyJams.

### General Settings
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `LOG_LEVEL` | Logging verbosity | No | `INFO` |
| `JELLYJAMS_DATA_DIR_HOST`| Path to JellyJams app data on host | ✅ Yes | `./jellyjams` |
| `ENABLE_WEB_UI` | Enable web interface | No | `true` |
| `WEB_PORT` | Web UI port | No | `5000` |
| `WEBUI_BASIC_AUTH_ENABLED` | Web UI password protection | No | `false` |
| `WEBUI_BASIC_AUTH_USERNAME` | Web UI user name | No | `admin` |
| `WEBUI_BASIC_AUTH_PASSWORD` | Web UI password | No | `admin` |

## 🎵 Playlist Generation Settings

Most playlist generation settings are now only configurable in the web UI, which is mostly self-explanitory.

### Smart Genre Grouping

JellyJams automatically groups similar genres into main categories to avoid creating too many overly specific playlists. This ensures a cleaner, more manageable playlist collection.

#### Genre Mapping Examples
| Specific Genres | Grouped As |
|----------------|------------|
| Alternative Rock, Indie Rock, Classic Rock, Hard Rock | **Rock Radio** |
| Hip Hop, Rap, Trap, Gangsta Rap | **Hip Hop Radio** |
| House, Techno, Trance, EDM, Electronic | **Electronic Radio** |
| Country, Country Rock, Bluegrass, Folk Country | **Country Radio** |
| Jazz, Smooth Jazz, Bebop, Jazz Fusion | **Jazz Radio** |
| Classical, Baroque, Romantic, Symphony | **Classical Radio** |
| Pop, Dance Pop, Synth Pop, Indie Pop | **Pop Radio** |

#### Benefits
- **Cleaner Organization**: Fewer, more meaningful playlists
- **Better Discovery**: Broader genre coverage in each playlist
- **Reduced Clutter**: Avoids dozens of micro-genre playlists
- **Consistent Naming**: Predictable "[Genre] Radio" format

## 👤 Personalized Playlists

> **⚠️ Important**: Personal playlists require the [Jellyfin Playback Reporting Plugin](https://github.com/jellyfin/jellyfin-plugin-playbackreporting) to be installed and enabled in your Jellyfin server. This plugin provides the listening statistics needed for Top Tracks and personalized recommendations.

## 🎯 Discovery Playlist Settings

Control the diversity of Discovery Mix playlists:

| Variable | Description | Default | Range |
|----------|-------------|---------|-------|
| `DISCOVERY_MAX_SONGS_PER_ALBUM` | Maximum songs from same album | `1` | `1-10` |
| `DISCOVERY_MAX_SONGS_PER_ARTIST` | Maximum songs from same artist | `2` | `1-20` |

**Example:**
```bash
# Very diverse - max 1 song per album, 1 per artist
DISCOVERY_MAX_SONGS_PER_ALBUM=1
DISCOVERY_MAX_SONGS_PER_ARTIST=1

# More relaxed - allow 2 per album, 3 per artist
DISCOVERY_MAX_SONGS_PER_ALBUM=2
DISCOVERY_MAX_SONGS_PER_ARTIST=3
```

## 🎨 Cover Art Settings

### Custom Cover Art
JellyJams supports custom playlist covers with intelligent fallback:

1. **Exact Match**: `"Top Tracks - Jonas.ext"`
2. **Generic Fallback**: `"Top Tracks - all.ext"`
3. **Spotify Fallback**: For artist playlists

**Supported Formats**: `.jpg`, `.jpeg`, `.png`, `.webp`, `.avif`, `.bmp`

**Docker Volume**: Put your 'cover' directory in the directory that you map to `/data`

#### Other Playlist Types
1. **Predefined Custom Covers** - Exact name matching
2. **Generic Fallbacks** - Type-specific defaults
3. **No cover art** - Playlist created without cover

### 🖼️ Custom Generated Covers

For artist playlists, JellyJams automatically generates professional covers:

| Feature | Description |
|---------|-------------|
| **Source Image** | Uses artist's `folder.ext` from music directory |
| **Text Overlay** | "This is [Artist]" with adaptive colors |
| **Unicode Support** | Handles special characters (alt‐J, Sigur Rós, Mötley Crüe) |
| **Quality** | High-resolution Webp |
| **Color Analysis** | Automatic brightness detection for optimal contrast |

#### Supported Cover File Base Names and Extension
- `folder`, `cover`, `artist`, `thumb`, `front`
- `.jpg`, `.jpeg`, `.png`, `.webp`, `.avif`, `.bmp`

### 📁 Predefined Custom Covers

Place custom images in your appdata/cover directory (mapped to `/data/cover/`):

#### Directory Structure Examples
```
/data/cover/
├── Top Tracks - Jonas.jpg          # Personal playlist (specific user)
├── Top Tracks - all.jpg            # Personal playlist (generic fallback)
├── Discovery Mix - Sarah.webp      # Personal playlist (specific user)
├── Discovery Mix - all.jpg         # Personal playlist (generic fallback)
├── Back to the 1990s.jpg           # Decade playlist
├── Back to the 1980s.png           # Decade playlist
├── Jazz Radio.jpg                  # Genre playlist
├── Rock Radio.png                  # Genre playlist
├── This is Beatles!.jpg            # Artist playlist (manual override)
└── This is - all.png               # Artist playlist (generic fallback)
```

#### Naming Conventions
| Playlist Type | Exact Match | Generic Fallback |
|---------------|-------------|------------------|
| **Personal** | `Top Tracks - Jonas.jpg` | `Top Tracks - all.jpg` |
| **Personal** | `Discovery Mix - Sarah.png` | `Discovery Mix - all.png` |
| **Decade** | `Back to the 1990s.jpg` | `Back to - all.jpg` |
| **Genre** | `Jazz Radio.jpg` | `Radio - all.jpg` |
| **Artist** | `This is Beatles!.jpg` | `This is - all.jpg` |

### 🔄 Update Covers Feature

Refresh cover art for existing playlists without regenerating playlists:

#### Web UI Usage
1. Navigate to **Playlists** page (`/playlists`)
2. Click **"Update Covers"** button
3. Monitor real-time progress with statistics
4. Page automatically refreshes when complete

#### How It Works
- **Selective Processing**: Focuses on artist playlists for efficiency
- **Multi-tier Approach**: Tries all cover art sources in priority order
- **Progress Tracking**: Shows updated/skipped/error counts
- **Timeout Protection**: 5-minute timeout for long operations
- **Error Handling**: Graceful fallbacks with detailed logging

#### When to Use
- After adding new cover art files to `/data/cover/`
- When Spotify integration settings change
- After updating music library with new artist folders
- To fix missing or corrupted cover art

### 🛠️ Cover Art Troubleshooting

#### Custom Generated Covers Not Working
**Symptoms**: Artist playlists have no cover art or fallback to album or generic covers

**Solutions**:
1. **Check Artist Primary Image**:
   - JellyJams tries to fetch the artist's primary image using the Jellyfin API first.
   - Does the artist have a primary image set in Jellyfin?
   - Music directory access is not required for this method.

1. **Check Music Directory Access**:
   - If getting the primary image from the API fails, the next step is searching the artist's directory.
   ```bash
   # Verify Docker volume mount includes music directory
   docker-compose logs jellyjams | grep "music directory"
   ```

2. **Verify Artist Folder Structure**:
   ```
   /your/music/directory/
   ├── Artist Name/
   │   ├── folder.jpg          # ✅ This works
   │   ├── cover.png           # ✅ This works
   │   └── Album/
   │       └── cover.webp      # ✅ Album image used as fallback
   └── Another Artist/
       └── artist.jpeg         # ✅ This works
   ```

3. **Check Unicode Issues**:
   - Look for encoding errors in logs
   - Special characters are automatically converted (alt‐J → alt-J)
   - Enable DEBUG logging for detailed character processing

4. **Font Issues**:
   ```bash
   # Check if PIL/Pillow is properly installed
   docker exec jellyjams python -c "from PIL import Image, ImageDraw, ImageFont; print('PIL OK')"
   ```

#### Predefined Covers Not Loading
**Symptoms**: Custom covers in `/data/cover/` are ignored

**Solutions**:
1. **Verify Docker Volume Mount**:
   - Put your 'cover' directory in your 'appdata' directory.
   ```yaml
   volumes:
     - /host/path/appdata:/data  # Must be mounted
   ```

2. **Check File Permissions**:
   ```bash
   # Ensure container can read cover files
   ls -la /host/path/appdata/cover/
   ```

3. **Verify Exact Naming**:
   - File names must match playlist names exactly
   - Case-sensitive matching
   - Include file extensions

4. **Supported Formats**:
   - `.jpg`, `.jpeg`, `.png`, `.webp`, `.avif`, `.bmp`
   - Other formats may not be recognized

#### Spotify Integration Issues
**Symptoms**: Spotify cover art not downloading

**Solutions**:
1. **Test Connection in Web UI**:
   - Go to Settings → Spotify Integration
   - Click "Test Connection"
   - Check statistics and error messages

2. **Verify Credentials**:
   ```bash
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   SPOTIFY_COVER_ART_ENABLED=true
   ```

3. **Check Rate Limits**:
   - Spotify API has rate limits
   - Enable DEBUG logging to see API responses
   - Consider reducing concurrent requests

#### Debug Logging
Enable comprehensive cover art debugging:
```bash
JELLYJAMS_LOG_LEVEL=DEBUG
```

This provides detailed information about:
- Artist folder search paths and results
- Cover art file detection and copying
- Unicode character processing
- Image generation steps
- Spotify API calls and responses
- Fallback system progression

## 🎧 Spotify Integration Settings

### Spotify API Configuration
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `SPOTIFY_CLIENT_ID` | Spotify API Client ID | For cover art | - |
| `SPOTIFY_CLIENT_SECRET` | Spotify API Client Secret | For cover art | - |
| `SPOTIFY_COVER_ART_ENABLED` | Enable Spotify cover downloads | No | `false` |

**Setup Steps:**
1. Create app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Get Client ID and Client Secret
3. Enable feature in settings

**Example:**
```bash
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here
SPOTIFY_COVER_ART_ENABLED=true
```

### Spotify Features
- Downloads cover art for "This is [Artist]!" playlists
- Automatic fallback if custom covers not found
- Statistics tracking and connection testing
- Rate limiting and error handling

## 🔧 System Settings

### Media Library Integration
| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `TRIGGER_LIBRARY_SCAN` | Auto-refresh Jellyfin library | `true` | `true`, `false` |

When enabled, JellyJams triggers a Jellyfin media library scan after playlist creation to ensure playlists appear immediately.

### Logging
| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `LOG_LEVEL` | Logging verbosity | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

**Log Levels:**
- `DEBUG` - Detailed debugging information
- `INFO` - General operational messages
- `WARNING` - Important warnings
- `ERROR` - Error messages only

## 🌐 Web UI Settings

### Settings Page Features
The web UI settings page (`/settings`) provides:

- **Connection Testing** - Test Jellyfin API connectivity
- **Metadata Loading** - Load available genres from your library
- **User Management** - Select users for personalized playlists
- **Spotify Integration** - Test Spotify API and view statistics
- **Live Validation** - Real-time setting validation
- **Persistent Storage** - Settings saved to `/data/config/settings.json`

### Settings Priority
1. **Web UI Settings** (highest priority)
2. **Environment Variables** (fallback)
3. **Default Values** (if nothing set)

## 🐳 Docker Volume Configuration

### Required Volumes
```yaml
volumes:
  # JellyJames app data (config, logs, cover)
  - /host/path/appdata:/data
  # Jellyfin playlists directory for playlist and art management
  - ${PLAYLIST_DIR_HOST}:/playlists
```

### Optional Volumes
```yaml
volumes:
  # Ready-only access to music directory for cover art generation
  - ${MUSIC_DIR_HOST}:${MUSIC_DIR_CONTAINER}:ro
```

### Unraid Configuration
For Unraid users, your volumes and associated variables may look something like this:

```yaml
volumes:
  - /mnt/user/appdata/jellyjams:/data
  - ${PLAYLIST_DIR_HOST}:/playlists
  - ${MUSIC_DIR_HOST}:${MUSIC_DIR_CONTAINER}:ro
```
```.env
PLAYLIST_DIR_HOST=/mnt/user/appdata/jellyfin/data/playlists
MUSIC_DIR_HOST=/mnt/user/media/data/music
MUSIC_DIR_CONTAINER=/mnt/user/media/data/music
```

## 📝 Examples

### Basic Setup
```bash
# .env file for basic setup
JELLYFIN_URL=http://localhost:8096
JELLYFIN_API_KEY=your_api_key_here
PLAYLIST_DIR_HOST=/path/to/jellyfin/config/data/playlists
PLAYLIST_TYPES=Genre,Year,Artist
MAX_TRACKS_PER_PLAYLIST=50
MIN_TRACKS_PER_PLAYLIST=10
```

### Advanced Setup with Personalization
```bash
# .env file for advanced setup
JELLYFIN_URL=https://jellyfin.example.com
JELLYFIN_API_KEY=your_api_key_here
PLAYLIST_DIR_HOST=/path/to/jellyfin/config/data/playlists
MUSIC_DIR_HOST=/host/path/to/music
MUSIC_DIR_CONTAINER=/jellyfin/container/path/to/music

# Playlist generation
PLAYLIST_TYPES=Genre,Year,Artist,Personal
MAX_TRACKS_PER_PLAYLIST=75
MIN_TRACKS_PER_PLAYLIST=15
MIN_ARTIST_DIVERSITY=8

# Personalized playlists
PERSONAL_PLAYLIST_USERS=jonas,sarah,mike
PERSONAL_PLAYLIST_MIN_USER_TRACKS=20

# Discovery diversity
DISCOVERY_MAX_SONGS_PER_ALBUM=1
DISCOVERY_MAX_SONGS_PER_ARTIST=2

# Spotify integration
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_COVER_ART_ENABLED=true

# System settings
TRIGGER_LIBRARY_SCAN=true
LOG_LEVEL=INFO
GENERATION_INTERVAL=12
```

### Genre Exclusion Examples
```bash
# Exclude spoken content
EXCLUDED_GENRES=Audiobook,Podcast,Spoken Word

# Exclude holiday music
EXCLUDED_GENRES=Christmas,Holiday

# Multiple exclusions
EXCLUDED_GENRES=Classical,Opera,Spoken Word,Audiobook,Podcast
```

## 🔍 Troubleshooting

### Common Issues

1. **Playlists not appearing in Jellyfin**
   - Ensure `TRIGGER_LIBRARY_SCAN=true`
   - Check Jellyfin API key permissions
   - Verify playlist folder is accessible
  
2. **Playlists not appearing in JellyJams**
   - Ensure `PLAYLIST_DIR_HOST` = your host path to the Jellyfin playlists directory
   - Verify Jellyfin playlists directory is mapped to /playlists

3. **Cover art not copying**
   - Verify file permissions on cover in your appdata directory
   - Check logs for detailed error messages

4. **Personalized playlists empty**
   - **Install Required Plugin**: Ensure [Jellyfin Playback Reporting Plugin](https://github.com/jellyfin/jellyfin-plugin-playbackreporting) is installed and enabled
   - Increase `PERSONAL_PLAYLIST_MIN_USER_TRACKS`
   - Check user has listening history in Jellyfin
   - Verify user selection in settings
   - Confirm plugin is collecting playback data

5. **Spotify integration not working**
   - Test connection in web UI settings
   - Verify Client ID and Secret are correct
   - Check Spotify app permissions

### Debug Mode
Enable detailed logging:
```bash
LOG_LEVEL=DEBUG
```

This provides comprehensive information about:
- Playlist creation process
- Cover art lookup and copying
- API calls and responses
- User filtering and selection
- Diversity control application

---

For additional help, check the application logs at `/data/logs/` or enable debug logging for detailed troubleshooting information. You may also check the container logs using `docker logs jellyjams` from the host CLI.
