# JellyJams 🎵
<p align="center">
  <img src="jellyjams.jpeg" alt="JellyJams Logo" />
</p>

**JellyJams** is a modern, standalone Docker container that automatically generates music playlists for your Jellyfin media server using the Jellyfin REST API. It features a beautiful dark-themed web UI for easy configuration and management.

![JellyJams Web UI](https://img.shields.io/badge/Web%20UI-Modern%20Dark%20Theme-8b5cf6)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ed)
![Docker Pulls](https://img.shields.io/docker/pulls/jonasmore/jellyjams?color=2496ed)
![Jellyfin](https://img.shields.io/badge/Jellyfin-API%20Integration-00a4dc)

![JellyJams Example](example.jpg)

## 🚧 Alpha Status & Feedback
JellyJams is currently in alpha. It's working well for me, but as my first coding project, I'm sure there are improvements to be made!
I'd love your feedback on:
- Installation experience
- Feature requests
- Performance with large libraries
- UI/UX suggestions


## ⚠️ Important Update (2025-09-09)

We changed how folders are bound into the container to simplify setup and improve compatibility.

- Update your `.env` to use these variables:
  - `JELLYJAMS_DATA_DIR_HOST=/mnt/user/appdata/jelljams`
  - `PLAYLIST_DIR_HOST=/mnt/user/appdata/jellyfin/data/playlists`
  - `MUSIC_DIR_HOST=/path/to/your/music` (e.g., `/mnt/user/media/data/music`)
  - `MUSIC_DIR_CONTAINER=/path/to/your/music` (must match the path that Jellyfin uses inside its container)
- The old `PLAYLIST_FOLDER` environment variable is no longer used. Please remove it if present.
- Most of the playlist settings have been moved to web UI only. Please reference `.env.example`.
- Compose volumes should look like this:
  - Host app data → `/data`
  - Jellyfin playlists → `/playlists`
  - Music (read-only) → `${MUSIC_DIR_HOST}:${MUSIC_DIR_CONTAINER}:ro`

See `SETTINGS.md` → Docker Volume Configuration for full details and Unraid examples.

### Early Development Notice

This project is evolving rapidly. Things may change significantly between releases. Always review the latest `README.md` and `SETTINGS.md` when upgrading to ensure your environment variables and volume mappings are correct.

## 🐳 Quick Start

Get JellyJams running in minutes with Docker:

Replace the placeholder paths with your real host directories:

```bash
docker run -d \
  --name jellyjams \
  -p 5000:5000 \
  -e JELLYFIN_URL=http://jellyfin:8096 \
  -e JELLYFIN_API_KEY=YOUR_API_KEY \
  -v /path/to/appdata/jellyjams:/data \
  -v /path/to/jellyfin/config/data/playlists:/playlists \
  jonasmore/jellyjams
```

📦 **Docker Hub**: [jonasmore/jellyjams](https://hub.docker.com/r/jonasmore/jellyjams)
## ✨ Features

### 🎵 Playlist Generation
- **Multiple Playlist Types** - Genre, Year, Artist, and Personalized playlists
- **Smart Genre Grouping** - Groups similar genres into main categories to avoid overly specific playlists (e.g., "Alternative Rock", "Indie Rock", "Classic Rock" → "Rock Radio")
- **Smart Naming** - Clean playlist names ("Rock Radio", "Back to 1980", "This is Beatles!")
- **Artist Diversity Control** - Configurable minimum artist diversity for genre/year playlists
- **Discovery Playlists** - Personalized recommendations with diversity controls (max songs per album/artist)
- **Jellyfin API Integration** - Creates playlists directly via REST API with proper privacy controls

### 👤 Personalized Features
- **User-Specific Playlists** - Private playlists based on individual listening habits
- **Multiple Playlist Types** - Top Tracks, Discovery Mix, Recent Favorites, Genre Mix
- **User Selection** - Choose specific users or generate for all users
- **Listening Analytics** - Based on play counts, favorites, and recent activity
- **Plugin Requirement** - Requires [Jellyfin Playback Reporting Plugin](https://github.com/jellyfin/jellyfin-plugin-playbackreporting) for listening statistics

### 🎨 Cover Art System
- **Multi-Tier Cover Art System** - Comprehensive fallback system for all playlist types
- **Custom Generated Covers** - "This is [Artist]" text overlays on artist folder images
- **Spotify Integration** - Automatic artist playlist cover downloads from Spotify
- **Predefined Custom Covers** - Manual cover art for specific playlists
- **Smart Fallbacks** - Generic covers per playlist type ("Top Tracks - all.ext")
- **Multi-format Support** - Searches for images in multiple formats (JPG, JPEG, PNG, WebP, AVIF, BMP)
- **Artist Folder Integration** - Uses existing folder.ext from music directories
- **Unicode Support** - Handles special characters in artist names (alt‐J, Sigur Rós, etc.)
- **Extension Preservation** - Maintains original image format when copying.
- **Generated Image Format** - Saves generated images as WebP for high quality and compression.

### 🌐 Modern Web Interface
- **Beautiful Dark Theme** - Modern, responsive design
- **Real-time Dashboard** - Connection status, playlist stats, and monitoring
- **Advanced Settings** - Comprehensive configuration with live validation
- **User Management** - Select users for personalized playlists
- **Playlist Viewing** - Browse playlist contents directly in the web UI

### ⚙️ Smart Configuration
- **Web UI Override** - Settings page overrides environment variables
- **Live Updates** - Changes apply immediately without container restart
- **Comprehensive Options** - 25+ configurable settings
- **Privacy Controls** - Separate settings for public vs private playlists

### 🔄 Automation & Integration
- **Scheduled Generation** - Configurable automatic playlist updates (default: 24 hours)
- **Media Library Scan** - Automatic Jellyfin library refresh after playlist creation
- **Docker Ready** - Easy deployment with Docker Compose
- **Unraid Support** - Dedicated docker-compose configuration
- **Comprehensive Logging** - Detailed operation tracking and debugging
- **Discord Notifications** - Optional Discord webhook notifications for playlist updates and cover art changes

## 🔒 Web UI Security

JellyJams includes optional basic authentication to protect the web interface:

### Basic Authentication
- **Default**: Disabled for easy setup
- **Configuration**: Via environment variables only

#### Environment Variables
```bash
WEBUI_BASIC_AUTH_ENABLED=true
WEBUI_BASIC_AUTH_USERNAME=your_username
WEBUI_BASIC_AUTH_PASSWORD=your_password
```

## 🎨 Cover Art System
- **Multi-Tier Cover Art System** - Comprehensive fallback system for all playlist types
- **Custom Generated Covers** - "This is [Artist]" text overlays on artist folder images
- **Spotify Integration** - Automatic artist playlist cover downloads from Spotify
- **Predefined Custom Covers** - Manual cover art for specific playlists
- **Smart Fallbacks** - Generic covers per playlist type ("Top Tracks - all.ext")
- **Multi-format Support** - Searches for images in multiple formats (JPG, JPEG, PNG, WebP, AVIF, BMP)
- **Artist Folder Integration** - Uses existing folder.ext from music directories
- **Unicode Support** - Handles special characters in artist names (alt‐J, Sigur Rós, etc.)
- **Extension Preservation** - Maintains original image format when copying.
- **Generated Image Format** - Saves generated images as WebP for high quality and compression.

### 🎯 Cover Art Priority System
1. **Custom Generated Covers** (Artist playlists)
2. **Spotify Cover Art** (Artist playlists, if enabled)
3. **Predefined Custom Covers** (Manual covers)
4. **Artist Folder Fallback** (Uses existing folder.ext)
5. **Generic Fallbacks** (Type-specific defaults)

#### 🖼️ Custom Generated Covers
For artist playlists, JellyJams automatically generates professional "This is [Artist]" covers:
- Uses artist's existing folder.ext as background
- Adds stylized text overlay with adaptive colors
- Handles Unicode characters (alt‐J, Sigur Rós, Mötley Crüe)
- High-quality PNG output with text shadows
- Automatic brightness analysis for optimal text contrast

#### 📁 Predefined Custom Covers
Place custom images in your cover directory (stored at `/data/cover`):
- Exact playlist name matching: `"Top Tracks - Jonas.ext"`
- Generic fallbacks: `"Top Tracks - all.ext"`
- Decade-specific covers: `"Back to the 1990s.ext"`
- Genre-specific covers: `"Jazz Radio.ext"`

#### 🎵 Artist Folder Integration
JellyJams can use existing cover art from your music library:
- Searches for `folder.ext`, `cover.ext`, `artist.ext` in artist directories
- You set the music directory path (in .env) to the same path you set in Jellyfin
- Case-insensitive artist folder matching
- Multiple image format support (JPG, PNG, WebP, AVIF, BMP)

#### 🔄 Update Covers Feature
Refresh cover art for existing playlists without regenerating:
- **Web UI Button**: "Update Covers" on playlists page
- **Multi-tier Processing**: Tries all cover art sources in priority order
- **Progress Tracking**: Real-time feedback with statistics
- **Selective Updates**: Focuses on artist playlists for efficiency
- **Error Handling**: Graceful fallbacks with detailed logging

### 🎯 Discovery Playlist Controls
Fine-tune discovery playlists for better variety:
- **Max songs per album** (default: 1)
- **Max songs per artist** (default: 2)
- Configurable via web UI settings

### 🔄 Automatic Library Refresh
JellyJams automatically triggers a Jellyfin media library scan after playlist creation to ensure playlists appear immediately in your Jellyfin interface. This can be disabled in .env.

## 📁 Generated Playlists

JellyJams creates playlists in the following format:

```
📁/playlists/
├── 📁Rock Radio/
│   └── playlist.xml
├── 📁Jazz Radio/
│   └── playlist.xml
├── 📁Back to the 1970s/
│   └── playlist.xml
└── 📁This is The Beatles!/
    └── playlist.xml
```

### Playlist XML Format

Playlists are saved in Jellyfin-compatible XML format:

```xml
<?xml version="1.0" encoding="utf-8"?>
<playlist xmlns="http://xspf.org/ns/0/">
  <title>JellyJams Genre: Rock</title>
  <trackList>
    <track>
      <location>file:///path/to/song.mp3</location>
      <title>Song Title</title>
      <creator>Artist Name</creator>
      <album>Album Name</album>
    </track>
  </trackList>
</playlist>
```

## 🐳 Docker Deployment

### Docker Compose (Recommended)

1. Use the included [docker-compose.yml](docker-compose.yml)
2. Copy [.env.example](.env.example). to .env
3. Enter your settings in your .env file

### Unraid Deployment

For Unraid users, bind app data to `/mnt/user/appdata/jellyjams/` for persistent storage. If you are using the included [docker-compose.yml](docker-compose.yml), set these values in your `.env` file.

```bash
JELLYJAMS_DATA_DIR_HOST=/mnt/user/appdata/jellyjams
PLAYLIST_DIR_HOST=/mnt/user/appdata/jellyfin/data/playlists
MUSIC_DIR_HOST=/mnt/user/media/data/music
MUSIC_DIR_CONTAINER=/mnt/user/media/data/music
```

## 🔧 API Integration

JellyJams uses the Jellyfin REST API to:

- Fetch music library metadata
- Parse genres, artists, and years
- Handle semicolon-separated genre strings
- Test connection status
- Retrieve audio item details
- Retrieve the primary image of artists

## 🎨 Web UI Features

### Dashboard
- Jellyfin connection status indicator
- Playlist generation statistics
- Quick action buttons
- Real-time status updates

### Settings
- Jellyfin server configuration
- Playlist generation options
- Genre exclusion management
- Scheduling configuration

### Playlist Management
- View all generated playlists
- Filter and search playlists
- Delete unwanted playlists
- Preview playlist contents

### Logs (a bit buggy)
- Real-time log viewing
- Log filtering and search
- Download log files
- Auto-refresh capability

## 🛠️ Development

### Project Structure

```
jellyjams/
├── .env.example           # Environment template
├── Dockerfile             # Container definition
├── docker-compose.yml     # Docker Compose config
└── app/                   # Container app files
    ├── entrypoint.sh          # App entrypoint
    ├── start.sh               # App startup script
    ├── requirements.txt       # Python dependencies
    ├── vibecodeplugin.py      # Main playlist generator
    ├── webapp.py              # Flask web UI
    └── cover                  # Customizable playlist images
        ├── Playlist Name.jpg
    └── static/                # WebUI resources
    └── templates/             # HTML templates
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Jellyfin](https://jellyfin.org/) - Amazing open-source media server
- [Bootstrap](https://getbootstrap.com/) - UI framework
- [Font Awesome](https://fontawesome.com/) - Icons
- [Inter Font](https://rsms.me/inter/) - Typography
- [Unsplash](https://unsplash.com/license) - Cover Images

## 📞 Support

- 🐛 **Issues**: [GitHub Issues](https://github.com/jonasmore/jellyjams/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/jonasmore/jellyjams/discussions)
- 🗒️ **Forum Post**: [Jellyfin Forum](https://forum.jellyfin.org/t-jellyjams-automatic-playlist-generator-for-jellyfin-alpha)
