# JellyJams 🎵

**JellyJams** is a modern, standalone Docker container that automatically generates music playlists for your Jellyfin media server using the Jellyfin REST API. It features a beautiful dark-themed web UI for easy configuration and management.

![JellyJams Web UI](https://img.shields.io/badge/Web%20UI-Modern%20Dark%20Theme-8b5cf6)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ed)
![Jellyfin](https://img.shields.io/badge/Jellyfin-API%20Integration-00a4dc)

## ✨ Features

- 🎵 **Automatic Playlist Generation** - Creates playlists by Genre, Year, and Artist
- 🌐 **Modern Web UI** - Beautiful dark-themed interface with responsive design
- ⚙️ **Smart Configuration** - Web UI settings override environment variables
- 🎨 **Genre Parsing** - Handles semicolon-separated genres correctly
- 📊 **Real-time Monitoring** - Dashboard with connection status and playlist stats
- 🔄 **Scheduled Generation** - Configurable automatic playlist updates
- 🐳 **Docker Ready** - Easy deployment with Docker Compose
- 📱 **Mobile Friendly** - Responsive design works on all devices

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Jellyfin media server with music library
- Jellyfin API key with appropriate permissions

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/jellyjams.git
   cd jellyjams
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env` with your settings:**
   ```bash
   # Essential container settings
   JELLYFIN_URL=https://your-jellyfin-server.com
   JELLYFIN_API_KEY=your_jellyfin_api_key_here
   ```

4. **Start the container:**
   ```bash
   docker-compose up -d
   ```

5. **Access the Web UI:**
   Open http://localhost:5000 in your browser

## 🎛️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JELLYFIN_URL` | Your Jellyfin server URL | Required |
| `JELLYFIN_API_KEY` | Jellyfin API key | Required |
| `PLAYLIST_FOLDER` | Container playlist directory | `/app/playlists` |
| `ENABLE_WEB_UI` | Enable web interface | `true` |
| `WEB_PORT` | Web UI port | `5000` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `GENERATION_INTERVAL` | Hours between auto-generation | `24` |
| `MAX_TRACKS_PER_PLAYLIST` | Maximum tracks per playlist | `100` |
| `MIN_TRACKS_PER_PLAYLIST` | Minimum tracks per playlist | `5` |
| `EXCLUDED_GENRES` | Comma-separated genres to exclude | `` |
| `SHUFFLE_TRACKS` | Shuffle tracks in playlists | `true` |
| `PLAYLIST_TYPES` | Types to generate (Genre,Year,Artist) | `Genre,Year,Artist` |

### Web UI Configuration

The web UI allows you to override environment variables with persistent settings:

- **Jellyfin Connection** - Test and configure API connection
- **Playlist Limits** - Set min/max tracks per playlist
- **Genre Exclusions** - Select genres to exclude from generation
- **Playlist Types** - Choose which types to generate
- **Scheduling** - Configure automatic generation interval

## 📁 Generated Playlists

JellyJams creates playlists in the following format:

```
📁 Playlists/
├── JellyJams Genre: Rock/
│   └── playlist.xml
├── JellyJams Genre: Jazz/
│   └── playlist.xml
├── JellyJams Year: 2023/
│   └── playlist.xml
└── JellyJams Artist: The Beatles/
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

```yaml
version: '3.8'

services:
  jellyjams:
    build: .
    container_name: jellyjams
    environment:
      - JELLYFIN_URL=${JELLYFIN_URL}
      - JELLYFIN_API_KEY=${JELLYFIN_API_KEY}
      - ENABLE_WEB_UI=true
    volumes:
      - jellyjams_playlists:/app/playlists
      - jellyjams_logs:/app/logs
      - jellyjams_config:/app/config
    ports:
      - "5000:5000"
    restart: unless-stopped

volumes:
  jellyjams_playlists:
  jellyjams_logs:
  jellyjams_config:
```

### Unraid Deployment

For Unraid users, use bind mounts to `/mnt/user/appdata/jellyjams/`:

```yaml
volumes:
  - /mnt/user/appdata/jellyjams/playlists:/app/playlists
  - /mnt/user/appdata/jellyjams/logs:/app/logs
  - /mnt/user/appdata/jellyjams/config:/app/config
```

## 🔧 API Integration

JellyJams uses the Jellyfin REST API to:

- Fetch music library metadata
- Parse genres, artists, and years
- Handle semicolon-separated genre strings
- Test connection status
- Retrieve audio item details

### Required API Permissions

Your Jellyfin API key needs access to:
- Read media library
- Access audio items
- Read metadata

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

### Logs
- Real-time log viewing
- Log filtering and search
- Download log files
- Auto-refresh capability

## 🛠️ Development

### Local Development

1. **Clone and setup:**
   ```bash
   git clone https://github.com/yourusername/jellyjams.git
   cd jellyjams
   cp .env.example .env
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run locally:**
   ```bash
   python webapp.py  # Web UI
   python vibecodeplugin.py  # Playlist generator
   ```

### Project Structure

```
jellyjams/
├── vibecodeplugin.py      # Main playlist generator
├── webapp.py              # Flask web UI
├── start.sh               # Container startup script
├── Dockerfile             # Container definition
├── docker-compose.yml     # Docker Compose config
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
└── templates/            # HTML templates
    ├── base.html
    ├── index.html
    ├── settings.html
    ├── playlists.html
    └── logs.html
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

## 📞 Support

- 🐛 **Issues**: [GitHub Issues](https://github.com/jonasmore/jellyjams/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/jonasmore/jellyjams/discussions)


