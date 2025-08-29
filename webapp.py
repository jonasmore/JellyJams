#!/usr/bin/env python3
"""
JellyJams Web UI - Configuration and Management Interface
"""

import os
import sys
import json
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from collections import deque
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, Response, send_file
from werkzeug.security import check_password_hash, generate_password_hash
import base64
from vibecodeplugin import Config, PlaylistGenerator, JellyfinAPI, setup_logging, SpotifyClient

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Global configuration
config = Config()

# Setup comprehensive logging for web UI
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Disable noisy loggers
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

logger = logging.getLogger('JellyJams.WebUI')
logger.setLevel(logging.DEBUG)
logger.info("🌐 JellyJams Web UI logging initialized")

# Serve logo asset
@app.route('/assets/logo.png')
def logo():
    """Serve the application logo"""
    logo_path = Path(__file__).parent / 'jellyjams-transparent.png'
    if logo_path.exists():
        return send_file(str(logo_path), mimetype='image/png')
    # Fallback: 404 if not found
    return '', 404

class ConfigManager:
    def __init__(self):
        self.config_file = '/app/config/settings.json'
        self.ensure_config_dir()
    
    def ensure_config_dir(self):
        """Ensure config directory exists"""
        Path(self.config_file).parent.mkdir(parents=True, exist_ok=True)
    
    def load_settings(self) -> Dict:
        """Load settings from JSON file with web UI taking precedence over environment variables"""
        # Start with environment variable defaults
        default_settings = {
            'jellyfin_url': config.jellyfin_url,
            'max_tracks_per_playlist': config.max_tracks_per_playlist,
            'min_tracks_per_playlist': config.min_tracks_per_playlist,
            'excluded_genres': config.excluded_genres,
            'excluded_artists': getattr(config, 'excluded_artists', []),
            'shuffle_tracks': config.shuffle_tracks,
            'playlist_types': config.playlist_types,
            'generation_interval': config.generation_interval,
            'log_level': config.log_level,
            'min_artist_diversity': getattr(config, 'min_artist_diversity', 5),
            'min_albums_per_artist': getattr(config, 'min_albums_per_artist', 2),
            'min_albums_per_decade': getattr(config, 'min_albums_per_decade', 3),
            'spotify_client_id': getattr(config, 'spotify_client_id', ''),
            'spotify_client_secret': getattr(config, 'spotify_client_secret', ''),
            'spotify_cover_art_enabled': getattr(config, 'spotify_cover_art_enabled', False),
            'enabled_genres': [],
            'enabled_years': [],
            'enabled_artists': [],
            'auto_generation': True,
            'personal_playlist_min_user_tracks': getattr(config, 'personal_playlist_min_user_tracks', 10),
            'discovery_max_songs_per_album': getattr(config, 'discovery_max_songs_per_album', 1),
            'discovery_max_songs_per_artist': getattr(config, 'discovery_max_songs_per_artist', 2),
            'min_albums_per_artist': getattr(config, 'min_albums_per_artist', 2),
            'min_albums_per_decade': getattr(config, 'min_albums_per_decade', 3),
            'trigger_library_scan': getattr(config, 'trigger_library_scan', True),
            # Scheduling settings
            'auto_generate_on_startup': getattr(config, 'auto_generate_on_startup', False),
            'schedule_mode': getattr(config, 'schedule_mode', 'manual'),
            'schedule_time': getattr(config, 'schedule_time', '00:00')
        }
        
        # Load and merge web UI settings (these take precedence)
        try:
            if Path(self.config_file).exists():
                with open(self.config_file, 'r') as f:
                    web_settings = json.load(f)
                    # Merge with defaults, but web UI settings override
                    default_settings.update(web_settings)
                    logger.info("Loaded web UI settings - these override environment variables")
        except Exception as e:
            logger.error(f"Error loading web UI settings: {e}")
        
        return default_settings
    
    def save_settings(self, settings: Dict):
        """Save settings to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(settings, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False
    
    def apply_settings(self, settings: Dict):
        """Apply settings to global config"""
        config.jellyfin_url = settings.get('jellyfin_url', config.jellyfin_url)
        
        # Ensure numeric settings are cast to integers (POSTed JSON may contain strings)
        try:
            config.max_tracks_per_playlist = int(settings.get('max_tracks_per_playlist', config.max_tracks_per_playlist))
        except (TypeError, ValueError):
            # Leave existing value if casting fails
            pass
        try:
            config.min_tracks_per_playlist = int(settings.get('min_tracks_per_playlist', config.min_tracks_per_playlist))
        except (TypeError, ValueError):
            pass
        
        config.excluded_genres = settings.get('excluded_genres', config.excluded_genres)
        config.excluded_artists = settings.get('excluded_artists', getattr(config, 'excluded_artists', []))
        config.shuffle_tracks = settings.get('shuffle_tracks', config.shuffle_tracks)
        config.playlist_types = settings.get('playlist_types', config.playlist_types)
        
        # Ensure numeric settings are cast to integers (POSTed JSON may contain strings)
        try:
            config.generation_interval = int(settings.get('generation_interval', config.generation_interval))
        except (TypeError, ValueError):
            pass
        
        config.log_level = settings.get('log_level', config.log_level)
        
        # Ensure numeric settings are cast to integers (POSTed JSON may contain strings)
        try:
            config.min_artist_diversity = int(settings.get('min_artist_diversity', getattr(config, 'min_artist_diversity', 5)))
        except (TypeError, ValueError):
            pass
        
        config.spotify_client_id = settings.get('spotify_client_id', getattr(config, 'spotify_client_id', ''))
        config.spotify_client_secret = settings.get('spotify_client_secret', getattr(config, 'spotify_client_secret', ''))
        config.spotify_cover_art_enabled = settings.get('spotify_cover_art_enabled', getattr(config, 'spotify_cover_art_enabled', False))
        
        # Apply playlist generation settings
        
        # Ensure numeric settings are cast to integers (POSTed JSON may contain strings)
        try:
            config.min_albums_per_artist = int(settings.get('min_albums_per_artist', getattr(config, 'min_albums_per_artist', 2)))
        except (TypeError, ValueError):
            pass
        try:
            config.min_albums_per_decade = int(settings.get('min_albums_per_decade', getattr(config, 'min_albums_per_decade', 3)))
        except (TypeError, ValueError):
            pass
        
        # Apply scheduling settings
        config.auto_generate_on_startup = settings.get('auto_generate_on_startup', getattr(config, 'auto_generate_on_startup', False))
        config.schedule_mode = settings.get('schedule_mode', getattr(config, 'schedule_mode', 'manual'))
        config.schedule_time = settings.get('schedule_time', getattr(config, 'schedule_time', '00:00'))

config_manager = ConfigManager()

# Basic authentication configuration
_auth_config_cache = None

def get_auth_config():
    """Get authentication configuration from environment variables only"""
    global _auth_config_cache
    
    # Cache the config to avoid repeated environment variable reads and logging
    if _auth_config_cache is not None:
        return _auth_config_cache
    
    env_enabled = os.getenv('WEBUI_BASIC_AUTH_ENABLED', '').lower()
    env_username = os.getenv('WEBUI_BASIC_AUTH_USERNAME', '')
    env_password = os.getenv('WEBUI_BASIC_AUTH_PASSWORD', '')
    
    # Check if authentication is explicitly enabled
    if env_enabled in ['true', '1', 'yes', 'on']:
        _auth_config_cache = {
            'enabled': True,
            'username': env_username or 'admin',
            'password': env_password or 'admin'
        }
        logger.info(f"🔐 Basic authentication enabled for user: {_auth_config_cache['username']}")
    else:
        _auth_config_cache = {'enabled': False, 'username': '', 'password': ''}
        logger.info("🔐 Basic authentication disabled")
    
    return _auth_config_cache

def check_auth(username, password):
    """Check if provided credentials are valid"""
    auth_config = get_auth_config()
    if not auth_config['enabled']:
        return True  # Authentication disabled
    
    return (username == auth_config['username'] and 
            password == auth_config['password'])

def authenticate():
    """Send a 401 response that enables basic auth"""
    return Response(
        'Authentication required.\n'
        'Please provide valid credentials to access JellyJams Web UI.', 401,
        {'WWW-Authenticate': 'Basic realm="JellyJams Web UI"'})

def requires_auth(f):
    """Decorator that requires authentication if enabled"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_config = get_auth_config()
        
        # If authentication is disabled, allow access
        if not auth_config['enabled']:
            return f(*args, **kwargs)
        
        # Check for valid credentials
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            logger.warning(f"🔒 Unauthorized access attempt to {request.endpoint}")
            return authenticate()
        
        # Only log authentication success for non-API routes to reduce log spam
        if not request.endpoint.startswith('api_'):
            logger.debug(f"🔓 Authenticated access to {request.endpoint}")
        return f(*args, **kwargs)
    return decorated

# Discord notification system
class DiscordNotifier:
    def __init__(self):
        self.enabled = False
        self.webhook_url = ''
        self._update_config()
    
    def _update_config(self):
        """Update Discord configuration from environment variables or web UI settings"""
        # Check environment variables first
        env_enabled = os.getenv('DISCORD_WEBHOOK_ENABLED', '').lower() in ['true', '1', 'yes', 'on']
        env_url = os.getenv('DISCORD_WEBHOOK_URL', '')
        
        if env_enabled or env_url:
            # Use environment variables
            self.enabled = env_enabled and bool(env_url)
            self.webhook_url = env_url
        else:
            # Fall back to web UI settings
            try:
                config_file = '/app/config/settings.json'
                if Path(config_file).exists():
                    with open(config_file, 'r') as f:
                        settings = json.load(f)
                    self.enabled = settings.get('discord_webhook_enabled', False) and bool(settings.get('discord_webhook_url', ''))
                    self.webhook_url = settings.get('discord_webhook_url', '')
            except Exception as e:
                logger.debug(f"Could not load Discord settings from web UI: {e}")
        
        if self.enabled and self.webhook_url:
            logger.info("🔔 Discord notifications enabled")
        elif self.enabled:
            logger.warning("🔔 Discord notifications enabled but no webhook URL provided")
            self.enabled = False
    
    def send_playlist_summary(self, stats, errors=None):
        """Send a summary of playlist generation/update to Discord"""
        if not self.enabled or not self.webhook_url:
            return
        
        try:
            # Build the summary message
            title = "🎵 JellyJams Playlist Update Summary"
            
            # Create summary lines
            summary_lines = []
            if stats.get('artist', {}).get('updated', 0) > 0:
                new_count = stats.get('artist', {}).get('new', 0)
                updated_count = stats.get('artist', {}).get('updated', 0)
                summary_lines.append(f"**{updated_count} Artist Playlists updated** ({new_count} new)")
            
            if stats.get('genre', {}).get('updated', 0) > 0:
                new_count = stats.get('genre', {}).get('new', 0)
                updated_count = stats.get('genre', {}).get('updated', 0)
                summary_lines.append(f"**{updated_count} Genre Playlists updated** ({new_count} new)")
            
            if stats.get('year', {}).get('updated', 0) > 0:
                new_count = stats.get('year', {}).get('new', 0)
                updated_count = stats.get('year', {}).get('updated', 0)
                summary_lines.append(f"**{updated_count} Decade Playlists updated** ({new_count} new)")
            
            if stats.get('personal', {}).get('updated', 0) > 0:
                new_count = stats.get('personal', {}).get('new', 0)
                updated_count = stats.get('personal', {}).get('updated', 0)
                summary_lines.append(f"**{updated_count} Personal Playlists updated** ({new_count} new)")
                
                # Add personal playlist users if available
                users = stats.get('personal', {}).get('users', [])
                if users:
                    summary_lines.append(f"Personal Playlist Users: {', '.join(users)}")
            
            # Add error information if present
            error_section = ""
            if errors and len(errors) > 0:
                error_count = len(errors)
                error_section = f"\n\n⚠️ **{error_count} Error{'s' if error_count > 1 else ''}:**\n"
                # Limit to 10 errors as requested
                for i, error in enumerate(errors[:10]):
                    error_section += f"• {error}\n"
                if len(errors) > 10:
                    error_section += f"• ... and {len(errors) - 10} more errors"
            
            # Build the embed
            description = "\n".join(summary_lines) if summary_lines else "No playlists were updated."
            description += error_section
            
            embed = {
                "title": title,
                "description": description,
                "color": 0x1DB954 if not errors else 0xFFA500,  # Spotify green or orange if errors
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "JellyJams",
                    "icon_url": "https://cdn.discordapp.com/attachments/placeholder/music_note.png"
                }
            }
            
            payload = {
                "embeds": [embed]
            }
            
            # Send the webhook
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("🔔 Discord notification sent successfully")
            
        except Exception as e:
            logger.error(f"🔔 Failed to send Discord notification: {e}")
    
    def send_cover_art_summary(self, updated_count, error_count, errors=None):
        """Send a summary of cover art updates to Discord"""
        if not self.enabled or not self.webhook_url:
            return
        
        try:
            title = "🎨 JellyJams Cover Art Update Summary"
            
            description = f"**{updated_count} playlist covers updated**"
            
            # Add error information if present
            if error_count > 0:
                description += f"\n\n⚠️ **{error_count} Error{'s' if error_count > 1 else ''}:**\n"
                if errors:
                    # Limit to 10 errors as requested
                    for i, error in enumerate(errors[:10]):
                        description += f"• {error}\n"
                    if len(errors) > 10:
                        description += f"• ... and {len(errors) - 10} more errors"
            
            embed = {
                "title": title,
                "description": description,
                "color": 0x9B59B6 if error_count == 0 else 0xFFA500,  # Purple or orange if errors
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "JellyJams",
                    "icon_url": "https://cdn.discordapp.com/attachments/placeholder/music_note.png"
                }
            }
            
            payload = {
                "embeds": [embed]
            }
            
            # Send the webhook
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("🔔 Discord cover art notification sent successfully")
            
        except Exception as e:
            logger.error(f"🔔 Failed to send Discord cover art notification: {e}")

# Initialize Discord notifier
discord_notifier = DiscordNotifier()

@app.route('/')
@requires_auth
def index():
    """Main dashboard"""
    settings = config_manager.load_settings()
    
    # Get playlist statistics
    playlist_stats = get_playlist_stats()
    
    # Get Jellyfin connection status
    jellyfin_api = JellyfinAPI(config, logger)
    jellyfin_connected = jellyfin_api.test_connection()
    
    return render_template('index.html', 
                         settings=settings,
                         playlist_stats=playlist_stats,
                         jellyfin_connected=jellyfin_connected)

@app.route('/settings')
@requires_auth
def settings():
    """Settings page - optimized for fast loading"""
    settings = config_manager.load_settings()
    
    # Load page immediately without fetching metadata (will be loaded via AJAX)
    return render_template('settings.html', settings=settings)

@app.route('/playlists')
@requires_auth
def playlists():
    """Playlist management page"""
    playlist_data = get_detailed_playlist_info()
    return render_template('playlists.html', 
                         playlists=playlist_data['playlists'], 
                         stats=playlist_data['stats'])



@app.route('/api/users')
@requires_auth
def api_users():
    """API endpoint to get Jellyfin users"""
    try:
        jellyfin_api = JellyfinAPI(config, logger)
        users = jellyfin_api.get_users()
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        logger.error(f"💥 Failed to get Jellyfin users: {e}")
        return jsonify({'success': False, 'message': 'Failed to get Jellyfin users.'})

@app.route('/logs')
@requires_auth
def logs():
    """Logs page - initial render shows last 100 lines"""
    def read_last_lines(path: str, n: int = 100) -> str:
        try:
            if not Path(path).exists():
                return "No logs available"
            # Efficient tail using deque
            with open(path, 'r', errors='ignore') as f:
                dq = deque(f, maxlen=n)
                return ''.join(dq)
        except Exception as e:
            return f"Error reading logs: {e}"

    log_file = '/app/logs/jellyjams.log'
    log_content = read_last_lines(log_file, 100)
    return render_template('logs.html', log_content=log_content)

@app.route('/api/logs_tail', methods=['GET'])
@requires_auth
def api_logs_tail():
    """API: return the last N lines of the main log file as plain text."""
    try:
        lines = int(request.args.get('lines', 100))
    except (TypeError, ValueError):
        lines = 100

    log_file = '/app/logs/jellyjams.log'

    def read_last_lines(path: str, n: int) -> str:
        try:
            if not Path(path).exists():
                return ""
            with open(path, 'r', errors='ignore') as f:
                dq = deque(f, maxlen=n)
                return ''.join(dq)
        except Exception as e:
            logger.error(f"Error tailing logs: {e}")
            return ""

    content = read_last_lines(log_file, lines)
    return jsonify({
        'lines': content,
        'line_count': len(content.split('\n')) if content else 0
    })

@app.route('/api/settings', methods=['GET', 'POST'])
@requires_auth
def api_settings():
    """API endpoint for settings"""
    if request.method == 'GET':
        settings = config_manager.load_settings()
        
        # Add Discord webhook settings (check environment variables first)
        discord_enabled_env = os.getenv('DISCORD_WEBHOOK_ENABLED', '').lower() in ['true', '1', 'yes', 'on']
        discord_url_env = os.getenv('DISCORD_WEBHOOK_URL', '')
        
        # Use environment variables if set, otherwise use web UI settings
        if discord_enabled_env or discord_url_env:
            settings['discord_webhook_enabled'] = discord_enabled_env
            settings['discord_webhook_url'] = discord_url_env
        else:
            settings['discord_webhook_enabled'] = settings.get('discord_webhook_enabled', False)
            settings['discord_webhook_url'] = settings.get('discord_webhook_url', '')
        
        # Return in a shape expected by the frontend JS (with success and settings keys)
        resp = jsonify({
            'success': True,
            'settings': settings
        })
        # Prevent caching so browser always gets latest settings
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        return resp
    
    elif request.method == 'POST':
        try:
            settings = request.json
            # Load previous settings to compute diffs for logging
            previous_settings = config_manager.load_settings()

            # Helper to redact sensitive values
            def _redact(key, value):
                key_l = (key or '').lower()
                if any(s in key_l for s in ['password', 'secret', 'webhook']):
                    return '***redacted***'
                return value

            # Compute changed keys (simple shallow diff)
            changed = {}
            for k, new_v in (settings or {}).items():
                old_v = previous_settings.get(k)
                if new_v != old_v:
                    changed[k] = {
                        'from': _redact(k, old_v),
                        'to': _redact(k, new_v)
                    }

            if changed:
                # Log a concise summary and some detailed lines
                logger.info(f"🛠️ Settings updated via Web UI: {len(changed)} keys changed")
                # Highlight common important fields if present
                for key in ['playlist_types', 'schedule_mode', 'schedule_time', 'generation_interval', 'auto_generate_on_startup']:
                    if key in changed:
                        logger.info(f"🔧 {key}: {changed[key]['from']} -> {changed[key]['to']}")
                # Log remaining changes (limit to avoid log spam)
                other_changes = [k for k in changed.keys() if k not in ['playlist_types', 'schedule_mode', 'schedule_time', 'generation_interval', 'auto_generate_on_startup']]
                for k in other_changes[:10]:
                    logger.debug(f"⚙️ {k}: {changed[k]['from']} -> {changed[k]['to']}")
                if len(other_changes) > 10:
                    logger.debug(f"… {len(other_changes) - 10} more changes not shown")

            if config_manager.save_settings(settings):
                config_manager.apply_settings(settings)
                return jsonify({'success': True, 'message': 'Settings saved successfully'})
            else:
                return jsonify({'success': False, 'message': 'Failed to save settings'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})

def save_web_ui_settings(new_settings):
    """Save settings to web UI settings file"""
    config_file = '/app/config/settings.json'
    config_dir = Path('/app/config')
    
    try:
        # Ensure config directory exists
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing settings if they exist
        existing_settings = {}
        if Path(config_file).exists():
            with open(config_file, 'r') as f:
                existing_settings = json.load(f)
        
        # Update with new settings
        existing_settings.update(new_settings)
        
        # Save updated settings
        with open(config_file, 'w') as f:
            json.dump(existing_settings, f, indent=2)
        
        logger.info(f"Saved web UI settings: {list(new_settings.keys())}")
    except Exception as e:
        logger.error(f"Error saving web UI settings: {e}")
        raise

@app.route('/api/generate', methods=['POST'])
@requires_auth
def api_generate():
    """API endpoint to trigger playlist generation"""
    try:
        logger.info("🎵 ========== API PLAYLIST GENERATION TRIGGERED ===========")
        logger.info(f"🔧 Current config: {config.playlist_types}")
        logger.info(f"🔧 Jellyfin URL: {config.jellyfin_url}")
        logger.info(f"🔧 API Key configured: {'Yes' if config.api_key else 'No'}")
        
        # Get playlist stats before generation
        stats_before = get_playlist_stats()
        
        # Import here to ensure logging is set up
        from vibecodeplugin import setup_logging
        
        # Setup comprehensive logging for the generator
        generator_logger = setup_logging(config)
        generator_logger.info("🎵 Creating PlaylistGenerator instance from API call")
        
        generator = PlaylistGenerator(config, generator_logger)
        logger.info("🎤 Starting playlist generation from web UI...")
        
        # Store errors for Discord notification
        generation_errors = []
        
        try:
            generator.generate_playlists()
        except Exception as gen_error:
            generation_errors.append(str(gen_error))
            raise
        
        # Get playlist stats after generation
        stats_after = get_playlist_stats()
        
        # Calculate changes for Discord notification
        discord_stats = {
            'artist': {
                'updated': stats_after.get('artist', 0),
                'new': max(0, stats_after.get('artist', 0) - stats_before.get('artist', 0))
            },
            'genre': {
                'updated': stats_after.get('genre', 0),
                'new': max(0, stats_after.get('genre', 0) - stats_before.get('genre', 0))
            },
            'year': {
                'updated': stats_after.get('year', 0),
                'new': max(0, stats_after.get('year', 0) - stats_before.get('year', 0))
            },
            'personal': {
                'updated': stats_after.get('personal', 0),
                'new': max(0, stats_after.get('personal', 0) - stats_before.get('personal', 0)),
                'users': []  # Will be populated if personal playlists are generated
            }
        }
        
        # Send Discord notification if any playlists were updated
        total_updated = sum(cat['updated'] for cat in discord_stats.values())
        if total_updated > 0 or generation_errors:
            discord_notifier.send_playlist_summary(discord_stats, generation_errors)
        
        logger.info("✅ Playlist generation completed successfully from API")
        return jsonify({'success': True, 'message': 'Playlist generation completed successfully'})
    except Exception as e:
        logger.error(f"❌ API playlist generation failed: {e}")
        logger.exception("Full error details:")
        
        # Send Discord notification for failed generation
        discord_notifier.send_playlist_summary({}, [str(e)])
        
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/generate_personalized', methods=['POST'])
@requires_auth
def api_generate_personalized():
    """API endpoint to trigger personalized playlist generation"""
    try:
        # Get playlist stats before generation
        stats_before = get_playlist_stats()
        
        generator = PlaylistGenerator(config, logger)
        
        # Get audio items first
        audio_items = generator.jellyfin.get_audio_items()
        if not audio_items:
            return jsonify({'success': False, 'message': 'No audio items found'})
        
        # Store errors for Discord notification
        generation_errors = []
        
        try:
            # Generate personalized playlists
            generator.generate_personalized_playlists(audio_items)
        except Exception as gen_error:
            generation_errors.append(str(gen_error))
            raise
        
        # Get playlist stats after generation
        stats_after = get_playlist_stats()
        
        # Calculate changes for Discord notification
        personal_updated = stats_after.get('personal', 0)
        personal_new = max(0, stats_after.get('personal', 0) - stats_before.get('personal', 0))
        
        # Get user list for personal playlists
        user_list = getattr(config, 'personal_playlist_users', [])
        
        discord_stats = {
            'personal': {
                'updated': personal_updated,
                'new': personal_new,
                'users': user_list
            }
        }
        
        # Send Discord notification if any personal playlists were updated
        if personal_updated > 0 or generation_errors:
            discord_notifier.send_playlist_summary(discord_stats, generation_errors)
        
        return jsonify({'success': True, 'message': 'Personalized playlist generation completed'})
    except Exception as e:
        logger.error(f"Error generating personalized playlists: {e}")
        
        # Send Discord notification for failed generation
        discord_notifier.send_playlist_summary({}, [str(e)])
        
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/delete_playlist', methods=['POST'])
@requires_auth
def api_delete_playlist():
    """API endpoint to delete a playlist"""
    try:
        playlist_name = request.json.get('playlist_name')
        if not playlist_name:
            return jsonify({'success': False, 'message': 'Playlist name required'})
        
        playlist_dir = Path(config.playlist_folder) / playlist_name
        if playlist_dir.exists():
            import shutil
            shutil.rmtree(playlist_dir)
            return jsonify({'success': True, 'message': f'Deleted playlist: {playlist_name}'})
        else:
            return jsonify({'success': False, 'message': 'Playlist not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/delete_all_playlists', methods=['POST'])
@requires_auth
def api_delete_all_playlists():
    """API endpoint to delete all playlists"""
    try:
        playlist_dir = Path(config.playlist_folder)
        if not playlist_dir.exists():
            return jsonify({'success': False, 'message': 'Playlist directory not found'})
        
        deleted_count = 0
        for playlist_folder in playlist_dir.iterdir():
            if playlist_folder.is_dir():
                import shutil
                shutil.rmtree(playlist_folder)
                deleted_count += 1
        
        logger.info(f"Deleted {deleted_count} playlists")
        return jsonify({
            'success': True, 
            'message': f'Successfully deleted {deleted_count} playlists'
        })
    except Exception as e:
        logger.error(f"Error deleting all playlists: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/cover/<path:playlist_name>', methods=['GET'])
@requires_auth
def api_cover_art(playlist_name):
    """API endpoint to serve cover art for playlists.
    Supports both 'folder.*' and 'cover.*' with common image extensions.
    """
    try:
        playlist_dir = Path(config.playlist_folder) / playlist_name
        logger.debug(f"Cover request for '{playlist_name}', resolved dir: {playlist_dir}")
        if not playlist_dir.exists():
            logger.debug(f"Playlist directory does not exist: {playlist_dir}")
            return '', 404
        
        # Search order: folder.* first (what generator writes), then cover.*
        names = ['folder', 'cover']
        exts = ['.jpg', '.jpeg', '.png', '.webp', '.bmp']
        mimetypes = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp'
        }
        
        try:
            existing = [p.name for p in playlist_dir.iterdir()]
            logger.debug(f"Existing files in dir: {existing}")
        except Exception as e:
            logger.debug(f"Failed to list directory {playlist_dir}: {e}")
            existing = []

        for base in names:
            for ext in exts:
                candidate = playlist_dir / f"{base}{ext}"
                logger.debug(f"Checking candidate cover: {candidate}")
                if candidate.exists():
                    return send_file(str(candidate), mimetype=mimetypes.get(ext, 'application/octet-stream'))
        
        # Not found
        logger.debug(f"No cover image found for '{playlist_name}' in {playlist_dir}")
        return '', 404
            
    except Exception as e:
        logger.error(f"Error serving cover art for {playlist_name}: {e}")
        return '', 404

@app.route('/api/spotify/test', methods=['POST'])
@requires_auth
def api_spotify_test():
    """API endpoint to test Spotify integration"""
    try:
        # Get the current Spotify client from the playlist generator
        from vibecodeplugin import PlaylistGenerator
        generator = PlaylistGenerator(config, logger)
        
        if not generator.spotify:
            return jsonify({
                'success': False,
                'message': 'Spotify client not initialized'
            })
        
        # Run the connection test
        test_result = generator.spotify.test_connection()
        
        return jsonify({
            'success': test_result['success'],
            'message': test_result['message'],
            'response_time': round(test_result['response_time'], 3),
            'timestamp': test_result['timestamp']
        })
        
    except Exception as e:
        logger.error(f"Error testing Spotify connection: {e}")
        return jsonify({
            'success': False,
            'message': f'Test failed: {str(e)}'
        })

@app.route('/api/spotify/stats', methods=['GET'])
@requires_auth
def api_spotify_stats():
    """API endpoint to get Spotify integration statistics"""
    try:
        # Get the current Spotify client from the playlist generator
        from vibecodeplugin import PlaylistGenerator
        generator = PlaylistGenerator(config, logger)
        
        if not generator.spotify:
            return jsonify({
                'enabled': False,
                'message': 'Spotify integration not enabled'
            })
        
        # Get statistics
        stats = generator.spotify.get_statistics()
        
        return jsonify({
            'enabled': True,
            'stats': {
                'total_attempts': stats['total_attempts'],
                'successful_downloads': stats['successful_downloads'],
                'failed_downloads': stats['failed_downloads'],
                'api_errors': stats['api_errors'],
                'success_rate': round(stats['success_rate'], 1),
                'avg_response_time': round(stats['avg_response_time'], 3),
                'min_response_time': round(stats['min_response_time'], 3),
                'max_response_time': round(stats['max_response_time'], 3),
                'last_test_time': stats['last_test_time'],
                'last_test_result': stats['last_test_result']
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Spotify statistics: {e}")
        return jsonify({
            'enabled': False,
            'message': f'Error retrieving statistics: {str(e)}'
        })

@app.route('/api/playlist_contents/<path:playlist_name>', methods=['GET'])
@requires_auth
def api_playlist_contents(playlist_name):
    """API endpoint to get playlist contents"""
    try:
        import xml.etree.ElementTree as ET
        
        playlist_dir = Path(config.playlist_folder) / playlist_name
        playlist_file = playlist_dir / 'playlist.xml'
        
        if not playlist_file.exists():
            return jsonify({'success': False, 'message': 'Playlist file not found'})
        
        # Parse the XML playlist file (Jellyfin format)
        tree = ET.parse(playlist_file)
        root = tree.getroot()
        
        tracks = []
        # Look for PlaylistItem elements with Path children
        for playlist_item in root.findall('.//PlaylistItem'):
            path_element = playlist_item.find('Path')
            if path_element is not None and path_element.text:
                file_path = path_element.text
                
                # Extract track info from file path
                import os
                filename = os.path.basename(file_path)
                
                # Try to parse filename for track info
                # Format is usually: "track_number - title.extension"
                title = filename
                artist = 'Unknown Artist'
                album = 'Unknown Album'
                
                # Extract from path structure: /data/music/Artist/Album/track.mp3
                path_parts = file_path.split('/')
                if len(path_parts) >= 4:
                    artist = path_parts[-3]  # Artist folder
                    album_info = path_parts[-2]  # Album folder
                    
                    # Clean up album info (remove year and extra info)
                    if ' - ' in album_info:
                        album_parts = album_info.split(' - ')
                        if len(album_parts) >= 3:
                            album = album_parts[2]  # Third part is usually album name
                        else:
                            album = album_parts[-1]  # Last part
                    else:
                        album = album_info
                
                # Clean up filename for title
                if filename.endswith('.mp3'):
                    title = filename[:-4]  # Remove .mp3 extension
                
                # Remove track number prefix if present (e.g., "01 - ")
                if ' - ' in title and title[:3].replace(' ', '').isdigit():
                    title = ' - '.join(title.split(' - ')[1:])
                
                track_info = {
                    'title': title,
                    'artist': artist,
                    'album': album,
                    'duration': '0',  # Duration not available in this format
                    'location': file_path
                }
                tracks.append(track_info)
        
        return jsonify({
            'success': True,
            'playlist_name': playlist_name,
            'track_count': len(tracks),
            'tracks': tracks
        })
    except Exception as e:
        logger.error(f"Error getting playlist contents for {playlist_name}: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/jellyfin_test')
@requires_auth
def api_jellyfin_test():
    """Test Jellyfin connection"""
    jellyfin_api = JellyfinAPI(config, logger)
    connected = jellyfin_api.test_connection()
    return jsonify({'connected': connected})

@app.route('/api/metadata')
@requires_auth
def api_metadata():
    """Get Jellyfin metadata - optimized with error handling"""
    try:
        jellyfin_api = JellyfinAPI(config, logger)
        
        # Test connection first
        if not jellyfin_api.test_connection():
            return jsonify({
                'success': False, 
                'message': 'Cannot connect to Jellyfin server',
                'genres': [],
                'years': [],
                'artists': []
            })
        
        metadata = get_jellyfin_metadata(jellyfin_api)
        return jsonify({
            'success': True,
            'genres': metadata.get('genres', []),
            'years': metadata.get('years', []),
            'artists': metadata.get('artists', [])
        })
    except Exception as e:
        logger.error(f"Error fetching metadata: {e}")
        return jsonify({
            'success': False,
            'message': str(e),
            'genres': [],
            'years': [],
            'artists': []
        })

@app.route('/api/artists')
@requires_auth
def api_artists():
    """Get all artists from Jellyfin for excluded artists functionality"""
    try:
        jellyfin_api = JellyfinAPI(config, logger)
        
        # Test connection first
        if not jellyfin_api.test_connection():
            return jsonify({
                'success': False, 
                'message': 'Cannot connect to Jellyfin server',
                'artists': []
            })
        
        metadata = get_jellyfin_metadata(jellyfin_api)
        artists = metadata.get('artists', [])
        
        return jsonify({
            'success': True,
            'artists': sorted(artists),  # Sort alphabetically for better UX
            'count': len(artists)
        })
    except Exception as e:
        logger.error(f"Error fetching artists: {e}")
        return jsonify({
            'success': False,
            'message': str(e),
            'artists': []
        })

@app.route('/api/update-covers', methods=['POST'])
@requires_auth
def api_update_covers():
    """Update cover art for existing playlists with optimized performance to prevent worker timeouts"""
    try:
        import time
        start_time = time.time()
        
        logger.info("🎨 Starting optimized cover art update process...")
        
        # Get playlist generator and Spotify client ONCE at startup
        config = Config()
        jellyfin_logger = setup_logging(config)
        generator = PlaylistGenerator(config, jellyfin_logger)
        spotify = SpotifyClient(config, jellyfin_logger)
        
        # Pre-cache Spotify configuration to avoid repeated checks
        spotify_enabled = spotify.is_enabled()
        spotify_available = spotify.spotify is not None
        
        logger.info(f"🔍 Configuration check - Spotify enabled: {spotify_enabled}, client available: {spotify_available}")
        logger.info(f"🔍 Config details - cover_art_enabled: {config.spotify_cover_art_enabled}, client_id: {bool(config.spotify_client_id)}, client_secret: {bool(config.spotify_client_secret)}")
        
        # Pre-load Jellyfin audio items cache to prevent repeated API calls
        logger.info("📡 Pre-loading Jellyfin audio items cache...")
        generator._get_cached_audio_items()  # This will cache all audio items for 30 minutes
        
        # Get all playlist directories
        playlist_folder = Path(config.playlist_folder)
        if not playlist_folder.exists():
            return jsonify({"error": "Playlist folder not found"}), 404
        
        playlist_dirs = [d for d in playlist_folder.iterdir() if d.is_dir()]
        total_count = len(playlist_dirs)
        
        # Optimized processing with smaller batches and longer timeout
        batch_size = 5  # Smaller batches for better responsiveness
        processed = 0
        timeout_limit = 180  # 3 minutes total timeout (reduced from 4)
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        logger.info(f"Processing {total_count} playlists in batches of {batch_size} with {timeout_limit}s timeout...")
        
        for playlist_dir in playlist_dirs:
            playlist_name = playlist_dir.name
            processed += 1
            
            # Check for timeout to prevent worker crashes
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout_limit:
                logger.warning(f"⏰ Timeout reached ({elapsed_time:.1f}s), stopping cover art updates")
                break
            
            # Add small delay between playlists to prevent overwhelming the system
            if processed > 1 and processed % batch_size == 0:
                time.sleep(0.1)  # 100ms pause between batches
            
            # Log progress every 5 playlists with timing info
            if processed % 5 == 0:
                avg_time_per_playlist = elapsed_time / processed if processed > 0 else 0
                estimated_remaining = (total_count - processed) * avg_time_per_playlist
                logger.info(f"📊 Progress: {processed}/{total_count} playlists processed ({elapsed_time:.1f}s elapsed, ~{estimated_remaining:.1f}s remaining)")
            
            try:
                # Handle all playlist types: artist, genre, decade, and personal playlists
                # Check for artist playlist pattern ("This is [Artist]" with optional "!" and extra characters)
                if playlist_name.startswith("This is "):
                    # Artist playlist - extract artist name and clean up extra characters
                    artist_name = playlist_name.replace("This is ", "")
                    # Remove exclamation marks and any trailing numbers/characters
                    import re
                    artist_name = re.sub(r'[!]+\d*$', '', artist_name).strip()
                    
                    # Only process if we have a valid artist name after cleaning
                    if artist_name:
                        cover_updated = False
                        
                        # Use pre-cached Spotify configuration (no more repeated checks!)
                        # Try Spotify cover art first if enabled
                        if spotify_enabled and spotify_available:
                            try:
                                logger.debug(f"🎵 Attempting Spotify cover art for {artist_name}")
                                spotify_success = spotify.get_artist_cover_art(artist_name, playlist_dir)
                                if spotify_success:
                                    logger.info(f"✅ Updated Spotify cover art for {artist_name}")
                                    cover_updated = True
                            except Exception as e:
                                logger.debug(f"Spotify cover art failed for {artist_name}: {e}")
                        elif not spotify_enabled:
                            logger.debug(f"⚠️ Spotify cover art skipped for {artist_name} - not enabled")
                        
                        # Try custom cover art generation if Spotify failed
                        if not cover_updated:
                            try:
                                # Use the existing generator instance (DO NOT create new one - it destroys the cache!)
                                # Find artist folder image first
                                artist_image_path = generator._find_artist_cover_image(artist_name)
                                if artist_image_path:
                                    logger.info(f"🖼️ Found artist image: {artist_image_path}")
                                    # Generate custom cover art with proper parameters
                                    cover_destination = playlist_dir / "folder.png"
                                    custom_success = generator._generate_custom_cover_art(artist_image_path, artist_name, cover_destination)
                                    if custom_success:
                                        logger.info(f"✅ Generated custom cover art for {artist_name}")
                                        cover_updated = True
                                else:
                                    logger.debug(f"No artist folder image found for {artist_name}")
                            except Exception as e:
                                logger.debug(f"Custom cover generation failed for {artist_name}: {e}")
                        
                        # Try folder fallback if both failed
                        if not cover_updated:
                            try:
                                generator = PlaylistGenerator(config, jellyfin_logger)
                                if hasattr(generator, '_try_artist_folder_fallback'):
                                    fallback_success = generator._try_artist_folder_fallback(artist_name, playlist_dir)
                                    if fallback_success:
                                        logger.info(f"✅ Updated folder cover art for {artist_name}")
                                        cover_updated = True
                            except Exception as e:
                                logger.debug(f"Folder fallback failed for {artist_name}: {e}")
                        
                        if cover_updated:
                            updated_count += 1
                        else:
                            logger.info(f"⏭️ No cover art update available for {artist_name}")
                    else:
                        # Invalid artist name after cleaning
                        logger.debug(f"⏭️ Skipping playlist with invalid artist name: {playlist_name}")
                        skipped_count += 1
                        
                elif playlist_name.endswith(" Radio"):
                    # Handle genre playlists (ending with " Radio")
                    logger.info(f"📻 Processing genre playlist: {playlist_name}")
                    
                    # Extract genre name by removing " Radio" suffix
                    genre_name = playlist_name.replace(" Radio", "")
                    
                    cover_updated = False
                    
                    # Use genre-specific cover art system
                    try:
                        cover_updated = generator._apply_genre_cover_art(playlist_name, genre_name, playlist_dir)
                        if cover_updated:
                            logger.info(f"✅ Applied genre cover art for {playlist_name}")
                        else:
                            logger.debug(f"No genre cover art found for {playlist_name}")
                    except Exception as e:
                        logger.debug(f"Genre cover art failed for {playlist_name}: {e}")
                    
                    if cover_updated:
                        updated_count += 1
                    else:
                        logger.info(f"⏭️ No cover art update available for {playlist_name}")
                        skipped_count += 1
                        
                elif playlist_name.startswith("Back to the "):
                    # Handle decade playlists (starting with "Back to the ")
                    logger.info(f"📅 Processing decade playlist: {playlist_name}")
                    
                    cover_updated = False
                    
                    # Use decade-specific cover art system
                    try:
                        cover_updated = generator._apply_decade_cover_art(playlist_name, playlist_dir)
                        if cover_updated:
                            logger.info(f"✅ Applied decade cover art for {playlist_name}")
                        else:
                            logger.debug(f"No decade cover art found for {playlist_name}")
                    except Exception as e:
                        logger.debug(f"Decade cover art failed for {playlist_name}: {e}")
                    
                    if cover_updated:
                        updated_count += 1
                    else:
                        logger.info(f"⏭️ No cover art update available for {playlist_name}")
                        skipped_count += 1
                        
                else:
                    # Handle personal playlists (everything else)
                    logger.info(f"🎵 Processing personal playlist: {playlist_name}")
                    
                    cover_updated = False
                    
                    # Use original cover art system - copy from /data/cover based on playlist name
                    try:
                        cover_updated = generator.copy_custom_cover_art(playlist_name, playlist_dir)
                        if cover_updated:
                            logger.info(f"✅ Applied cover art for personal playlist: {playlist_name}")
                        else:
                            logger.debug(f"No cover art found in /data/cover for personal playlist: {playlist_name}")
                    except Exception as e:
                        logger.debug(f"Cover art copy failed for personal playlist {playlist_name}: {e}")
                    
                    if cover_updated:
                        updated_count += 1
                    else:
                        logger.info(f"⏭️ No cover art update available for {playlist_name}")
                        skipped_count += 1
                        
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error updating cover for {playlist_name}: {e}")
        
        # Return results
        message = f"Cover art update complete: {updated_count} updated, {skipped_count} skipped, {error_count} errors"
        logger.info(f"🎨 {message}")
        
        # Send Discord notification for cover art updates
        if updated_count > 0 or error_count > 0:
            # Collect error messages for Discord notification (limit to 10)
            error_messages = []
            if hasattr(locals(), 'cover_errors') and cover_errors:
                error_messages = cover_errors[:10]
            
            discord_notifier.send_cover_art_summary(updated_count, error_count, error_messages)
        
        return jsonify({
            'success': True,
            'message': message,
            'updated': updated_count,
            'skipped': skipped_count,
            'errors': error_count
        })
        
    except Exception as e:
        logger.error(f"Error in cover art update: {e}")
        
        # Send Discord notification for cover art update failure
        discord_notifier.send_cover_art_summary(0, 1, [str(e)])
        
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/user_settings', methods=['GET'])
@requires_auth
def api_get_user_settings():
    """Get current user settings for personalized playlists"""
    try:
        return jsonify({
            'success': True,
            'settings': {
                'personal_playlist_users': config.personal_playlist_users,
                'personal_playlist_new_users_default': config.personal_playlist_new_users_default,
                'personal_playlist_min_user_tracks': config.personal_playlist_min_user_tracks
            }
        })
    except Exception as e:
        logger.error(f"Error getting user settings: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/user_settings', methods=['POST'])
@requires_auth
def api_save_user_settings():
    """Save user settings for personalized playlists"""
    try:
        data = request.json
        
        # Update config object
        if 'personal_playlist_users' in data:
            config.personal_playlist_users = data['personal_playlist_users']
        if 'personal_playlist_new_users_default' in data:
            config.personal_playlist_new_users_default = bool(data['personal_playlist_new_users_default'])
        if 'personal_playlist_min_user_tracks' in data:
            config.personal_playlist_min_user_tracks = int(data['personal_playlist_min_user_tracks'])
        
        # Save to web UI settings file
        save_web_ui_settings({
            'personal_playlist_users': config.personal_playlist_users,
            'personal_playlist_new_users_default': config.personal_playlist_new_users_default,
            'personal_playlist_min_user_tracks': config.personal_playlist_min_user_tracks
        })
        
        return jsonify({'success': True, 'message': 'User settings saved successfully'})
    except Exception as e:
        logger.error(f"Error saving user settings: {e}")
        return jsonify({'success': False, 'message': str(e)})

def get_playlist_stats():
    """Get playlist statistics using the same categorization logic as get_detailed_playlist_info"""
    try:
        playlist_dir = Path(config.playlist_folder)
        if not playlist_dir.exists():
            return {'total': 0, 'genre': 0, 'year': 0, 'artist': 0, 'personal': 0}
        
        stats = {
            'total': 0,
            'genre': 0,
            'year': 0,
            'artist': 0,
            'personal': 0
        }
        
        for playlist_path in playlist_dir.iterdir():
            if playlist_path.is_dir():
                xml_file = playlist_path / 'playlist.xml'
                if xml_file.exists():
                    playlist_name = playlist_path.name
                    stats['total'] += 1
                    
                    # Use same categorization logic as get_detailed_playlist_info
                    if playlist_name.startswith('This is '):
                        stats['artist'] += 1
                    elif playlist_name.startswith('Back to the '):
                        stats['year'] += 1
                    elif playlist_name in ['Top Tracks - all', 'Discovery Mix', 'Recent Favorites', 'Genre Mix']:
                        stats['personal'] += 1
                    else:
                        # Check if it's a genre playlist (not starting with special prefixes)
                        if not any(playlist_name.startswith(prefix) for prefix in ['This is ', 'Back to the ', 'Top Tracks', 'Discovery', 'Recent', 'Genre']):
                            stats['genre'] += 1
                        else:
                            stats['personal'] += 1
        
        return stats
    except Exception as e:
        logger.error(f"Error getting playlist stats: {e}")
        return {'total': 0, 'genre': 0, 'year': 0, 'artist': 0, 'personal': 0}

def get_detailed_playlist_info():
    """Get detailed playlist information with proper categorization"""
    try:
        playlist_dir = Path(config.playlist_folder)
        if not playlist_dir.exists():
            return {
                'playlists': [],
                'stats': {
                    'total': 0,
                    'genre': 0,
                    'year': 0,
                    'artist': 0,
                    'personal': 0
                }
            }
        
        playlists = []
        stats = {
            'total': 0,
            'genre': 0,
            'year': 0,
            'artist': 0,
            'personal': 0
        }
        
        for playlist_path in playlist_dir.iterdir():
            if playlist_path.is_dir():
                xml_file = playlist_path / 'playlist.xml'
                if xml_file.exists():
                    # Get file stats
                    stat = xml_file.stat()
                    # Modified time comes from the playlist file (updates when overwritten/changed)
                    modified = datetime.fromtimestamp(stat.st_mtime)

                    # Stable created time handling: persist a created.txt alongside the playlist
                    created_file = playlist_path / 'created.txt'
                    created = None
                    if created_file.exists():
                        try:
                            created_text = created_file.read_text(encoding='utf-8').strip()
                            # Support both ISO and formatted timestamps
                            try:
                                created = datetime.fromisoformat(created_text)
                            except ValueError:
                                created = datetime.strptime(created_text, '%Y-%m-%d %H:%M:%S')
                        except Exception:
                            created = None
                    if created is None:
                        # Infer a best-effort creation time from available filesystem timestamps
                        # Note: st_ctime on Linux is ctime (metadata change), so prefer the oldest among candidates
                        candidates = [
                            stat.st_mtime,            # xml modified
                            stat.st_ctime             # xml ctime/change time
                        ]
                        try:
                            dir_stat = playlist_path.stat()
                            candidates.extend([dir_stat.st_mtime, dir_stat.st_ctime])
                        except Exception:
                            pass
                        try:
                            # Consider cover image if present as an additional hint
                            for base in ['folder', 'cover']:
                                for ext in ['.png', '.jpg', '.jpeg']:
                                    cf = playlist_path / f"{base}{ext}"
                                    if cf.exists():
                                        cfs = cf.stat()
                                        candidates.extend([cfs.st_mtime, cfs.st_ctime])
                        except Exception:
                            pass

                        # Choose the earliest plausible timestamp
                        created_ts = min(candidates) if candidates else stat.st_mtime
                        created = datetime.fromtimestamp(created_ts)

                        # Persist for future stable display
                        try:
                            created_file.write_text(created.isoformat(), encoding='utf-8')
                        except Exception:
                            # Non-fatal if we cannot write; UI will still show inferred value
                            pass
                    
                    # Try to get track count from XML
                    track_count = 0
                    try:
                        import xml.etree.ElementTree as ET
                        tree = ET.parse(xml_file)
                        playlist_items = tree.find('PlaylistItems')
                        if playlist_items is not None:
                            track_count = len(playlist_items.findall('PlaylistItem'))
                    except:
                        pass
                    
                    # Determine playlist category
                    playlist_name = playlist_path.name
                    category = 'personal'  # Default category
                    
                    if playlist_name.startswith('This is '):
                        category = 'artist'
                        stats['artist'] += 1
                    elif playlist_name.startswith('Back to the '):
                        category = 'year'
                        stats['year'] += 1
                    elif playlist_name in ['Top Tracks - all', 'Discovery Mix', 'Recent Favorites', 'Genre Mix']:
                        category = 'personal'
                        stats['personal'] += 1
                    else:
                        # Check if it's a genre playlist (not starting with special prefixes)
                        # Genre playlists are typically just the genre name
                        if not any(playlist_name.startswith(prefix) for prefix in ['This is ', 'Back to the ', 'Top Tracks', 'Discovery', 'Recent', 'Genre']):
                            category = 'genre'
                            stats['genre'] += 1
                        else:
                            stats['personal'] += 1
                    
                    stats['total'] += 1
                    
                    playlists.append({
                        'name': playlist_name,
                        'category': category,
                        'track_count': track_count,
                        'created': created.strftime('%Y-%m-%d %H:%M:%S'),
                        'modified': modified.strftime('%Y-%m-%d %H:%M:%S'),
                        'size': xml_file.stat().st_size
                    })
        
        return {
            'playlists': sorted(playlists, key=lambda x: x['name']),
            'stats': stats
        }
    except Exception as e:
        logger.error(f"Error getting playlist info: {e}")
        return {
            'playlists': [],
            'stats': {
                'total': 0,
                'genre': 0,
                'year': 0,
                'artist': 0,
                'personal': 0
            }
        }

def get_jellyfin_metadata(jellyfin_api):
    """Get available genres, years, and artists from Jellyfin"""
    try:
        audio_items = jellyfin_api.get_audio_items()
        
        genres = set()
        years = set()
        artists = set()
        
        for item in audio_items:
            # Parse genres - handle both list and semicolon-separated string formats
            if item.get('Genres'):
                if isinstance(item['Genres'], list):
                    for genre_item in item['Genres']:
                        if isinstance(genre_item, str) and ';' in genre_item:
                            # Split semicolon-separated genres
                            genres.update([g.strip() for g in genre_item.split(';') if g.strip()])
                        else:
                            genres.add(genre_item)
                elif isinstance(item['Genres'], str):
                    # Handle string format with semicolons
                    if ';' in item['Genres']:
                        genres.update([g.strip() for g in item['Genres'].split(';') if g.strip()])
                    else:
                        genres.add(item['Genres'])
            
            # Parse years
            if item.get('ProductionYear'):
                years.add(item['ProductionYear'])
            
            # Parse artists - handle semicolon-separated artists too
            if item.get('Artists'):
                if isinstance(item['Artists'], list):
                    for artist_item in item['Artists']:
                        if isinstance(artist_item, str) and ';' in artist_item:
                            # Split semicolon-separated artists
                            artists.update([a.strip() for a in artist_item.split(';') if a.strip()])
                        else:
                            artists.add(artist_item)
                elif isinstance(item['Artists'], str):
                    # Handle string format with semicolons
                    if ';' in item['Artists']:
                        artists.update([a.strip() for a in item['Artists'].split(';') if a.strip()])
                    else:
                        artists.add(item['Artists'])
        
        return {
            'genres': sorted(list(genres)),
            'years': sorted(list(years), reverse=True),
            'artists': sorted(list(artists))
        }
    except Exception as e:
        logger.error(f"Error getting Jellyfin metadata: {e}")
        return {'genres': [], 'years': [], 'artists': []}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
