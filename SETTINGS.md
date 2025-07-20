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

## 🔧 Configuration Methods

JellyJams supports two configuration methods:

### 1. Environment Variables
Set in your `.env` file or Docker environment. These serve as defaults.

### 2. Web UI Settings
Override environment variables through the web interface at `http://localhost:5000/settings`. These settings are persistent and take precedence over environment variables.

## 🎯 Essential Settings

### Jellyfin Connection
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `JELLYFIN_URL` | Your Jellyfin server URL | ✅ Yes | - |
| `JELLYFIN_API_KEY` | Jellyfin API key with media access | ✅ Yes | - |

**Example:**
```bash
JELLYFIN_URL=https://jellyfin.example.com
JELLYFIN_API_KEY=your_32_character_api_key_here
```

### Container Settings
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `PLAYLIST_FOLDER` | Container directory for playlists | No | `/app/playlists` |
| `ENABLE_WEB_UI` | Enable web interface | No | `true` |
| `WEB_PORT` | Web UI port | No | `5000` |
| `LOG_LEVEL` | Logging verbosity | No | `INFO` |

## 🎵 Playlist Generation Settings

### Basic Playlist Control
| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `PLAYLIST_TYPES` | Types of playlists to generate | `Genre,Year,Artist` | `Genre`, `Year`, `Artist`, `Personal` |
| `MAX_TRACKS_PER_PLAYLIST` | Maximum tracks per playlist | `100` | `1-1000` |
| `MIN_TRACKS_PER_PLAYLIST` | Minimum tracks required | `5` | `1-100` |
| `SHUFFLE_TRACKS` | Randomize track order | `true` | `true`, `false` |
| `EXCLUDED_GENRES` | Genres to skip (comma-separated) | `` | Any genre names |

**Example:**
```bash
PLAYLIST_TYPES=Genre,Year,Artist,Personal
MAX_TRACKS_PER_PLAYLIST=50
MIN_TRACKS_PER_PLAYLIST=10
SHUFFLE_TRACKS=true
EXCLUDED_GENRES=Spoken Word,Audiobook,Podcast
```

### Artist Diversity Control
| Variable | Description | Default | Range |
|----------|-------------|---------|-------|
| `MIN_ARTIST_DIVERSITY` | Minimum different artists for genre/year playlists | `5` | `1-50` |

This ensures genre and year playlists have sufficient artist variety. Playlists with fewer unique artists than this threshold won't be created.

### Scheduling
| Variable | Description | Default | Range |
|----------|-------------|---------|-------|
| `GENERATION_INTERVAL` | Hours between automatic generation | `24` | `1-168` |

## 👤 Personalized Playlist Settings

### User Selection
| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `PERSONAL_PLAYLIST_USERS` | Users for personalized playlists | `all` | `all` or comma-separated usernames |
| `PERSONAL_PLAYLIST_NEW_USERS_DEFAULT` | Include new users automatically | `true` | `true`, `false` |
| `PERSONAL_PLAYLIST_MIN_USER_TRACKS` | Minimum user tracks required | `10` | `1-100` |

**Examples:**
```bash
# Generate for all users
PERSONAL_PLAYLIST_USERS=all

# Generate for specific users only
PERSONAL_PLAYLIST_USERS=jonas,mike,sarah

# Require at least 25 tracks for personalized playlists
PERSONAL_PLAYLIST_MIN_USER_TRACKS=25
```

### Personalized Playlist Types
When `Personal` is included in `PLAYLIST_TYPES`, JellyJams generates:

1. **Top Tracks - [Username]** - Most played songs
2. **Discovery Mix - [Username]** - Personalized recommendations
3. **Recent Favorites - [Username]** - Recently played/favorited
4. **Genre Mix - [Username]** - Mixed from user's preferred genres

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

1. **Exact Match**: `"Top Tracks - Jonas.jpg"`
2. **Generic Fallback**: `"Top Tracks - all.png"`
3. **Spotify Fallback**: For artist playlists

**Supported Formats**: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`

**Docker Volume**: Map your cover directory to `/app/cover`

```yaml
volumes:
  - /path/to/your/covers:/app/cover
```

### Cover Art Examples
```
/your/cover/directory/
├── Top Tracks - Jonas.jpg          # Specific user
├── Top Tracks - all.png            # Generic fallback
├── Discovery Mix - Sarah.webp      # Specific user
├── Discovery Mix - all.jpg         # Generic fallback
├── This is Beatles!.jpg            # Specific artist
└── This is - all.png               # Generic artist fallback
```

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
- **Persistent Storage** - Settings saved to `/app/config/settings.json`

### Settings Priority
1. **Web UI Settings** (highest priority)
2. **Environment Variables** (fallback)
3. **Default Values** (if nothing set)

## 🐳 Docker Volume Configuration

### Required Volumes
```yaml
volumes:
  - /host/path/playlists:/app/playlists     # Playlist storage
  - /host/path/logs:/app/logs               # Application logs
  - /host/path/config:/app/config           # Web UI settings
```

### Optional Volumes
```yaml
volumes:
  - /host/path/covers:/app/cover            # Custom cover art
```

### Unraid Configuration
For Unraid users, use the provided `docker-compose-unraid.yml`:

```yaml
volumes:
  - /mnt/user/appdata/jellyjams/playlists:/app/playlists
  - /mnt/user/appdata/jellyjams/logs:/app/logs
  - /mnt/user/appdata/jellyjams/config:/app/config
  - /mnt/user/appdata/jellyjams/cover:/app/cover
```

## 📝 Examples

### Basic Setup
```bash
# .env file for basic setup
JELLYFIN_URL=http://localhost:8096
JELLYFIN_API_KEY=your_api_key_here
PLAYLIST_TYPES=Genre,Year,Artist
MAX_TRACKS_PER_PLAYLIST=50
MIN_TRACKS_PER_PLAYLIST=10
```

### Advanced Setup with Personalization
```bash
# .env file for advanced setup
JELLYFIN_URL=https://jellyfin.example.com
JELLYFIN_API_KEY=your_api_key_here

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

2. **Cover art not copying**
   - Check Docker volume mount for `/app/cover`
   - Verify file permissions on cover directory
   - Check logs for detailed error messages

3. **Personalized playlists empty**
   - Increase `PERSONAL_PLAYLIST_MIN_USER_TRACKS`
   - Check user has listening history in Jellyfin
   - Verify user selection in settings

4. **Spotify integration not working**
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

For additional help, check the application logs at `/app/logs/` or enable debug logging for detailed troubleshooting information.
