#!/usr/bin/env python3
"""
JellyJams Web UI - Configuration and Management Interface
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from vibecodeplugin import Config, PlaylistGenerator, JellyfinAPI

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Global configuration
config = Config()
logger = logging.getLogger('JellyJams.WebUI')

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
            'shuffle_tracks': config.shuffle_tracks,
            'playlist_types': config.playlist_types,
            'generation_interval': config.generation_interval,
            'log_level': config.log_level,
            'min_artist_diversity': getattr(config, 'min_artist_diversity', 5),
            'spotify_client_id': getattr(config, 'spotify_client_id', ''),
            'spotify_client_secret': getattr(config, 'spotify_client_secret', ''),
            'spotify_cover_art_enabled': getattr(config, 'spotify_cover_art_enabled', False),
            'enabled_genres': [],
            'enabled_years': [],
            'enabled_artists': [],
            'auto_generation': True
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
        config.max_tracks_per_playlist = settings.get('max_tracks_per_playlist', config.max_tracks_per_playlist)
        config.min_tracks_per_playlist = settings.get('min_tracks_per_playlist', config.min_tracks_per_playlist)
        config.excluded_genres = settings.get('excluded_genres', config.excluded_genres)
        config.shuffle_tracks = settings.get('shuffle_tracks', config.shuffle_tracks)
        config.playlist_types = settings.get('playlist_types', config.playlist_types)
        config.generation_interval = settings.get('generation_interval', config.generation_interval)
        config.log_level = settings.get('log_level', config.log_level)
        config.min_artist_diversity = settings.get('min_artist_diversity', getattr(config, 'min_artist_diversity', 5))
        config.spotify_client_id = settings.get('spotify_client_id', getattr(config, 'spotify_client_id', ''))
        config.spotify_client_secret = settings.get('spotify_client_secret', getattr(config, 'spotify_client_secret', ''))
        config.spotify_cover_art_enabled = settings.get('spotify_cover_art_enabled', getattr(config, 'spotify_cover_art_enabled', False))

config_manager = ConfigManager()

@app.route('/')
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
def settings():
    """Settings page - optimized for fast loading"""
    settings = config_manager.load_settings()
    
    # Load page immediately without fetching metadata (will be loaded via AJAX)
    return render_template('settings.html', settings=settings)

@app.route('/playlists')
def playlists():
    """Playlist management page"""
    playlist_info = get_detailed_playlist_info()
    return render_template('playlists.html', playlists=playlist_info)

@app.route('/users')
def users():
    """User management page for personalized playlists"""
    return render_template('users.html')

@app.route('/logs')
def logs():
    """View logs"""
    try:
        log_file = '/app/logs/vibecodeplugin.log'
        if Path(log_file).exists():
            with open(log_file, 'r') as f:
                log_content = f.read()
        else:
            log_content = "No logs available"
    except Exception as e:
        log_content = f"Error reading logs: {e}"
    
    return render_template('logs.html', log_content=log_content)

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """API endpoint for settings"""
    if request.method == 'GET':
        return jsonify(config_manager.load_settings())
    
    elif request.method == 'POST':
        try:
            settings = request.json
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
def api_generate():
    """API endpoint to trigger playlist generation"""
    try:
        generator = PlaylistGenerator(config, logger)
        generator.generate_playlists()
        return jsonify({'success': True, 'message': 'Playlist generation completed'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/generate_personalized', methods=['POST'])
def api_generate_personalized():
    """API endpoint to trigger personalized playlist generation"""
    try:
        generator = PlaylistGenerator(config, logger)
        
        # Get audio items first
        audio_items = generator.jellyfin.get_audio_items()
        if not audio_items:
            return jsonify({'success': False, 'message': 'No audio items found'})
        
        # Generate personalized playlists
        generator.generate_personalized_playlists(audio_items)
        return jsonify({'success': True, 'message': 'Personalized playlist generation completed'})
    except Exception as e:
        logger.error(f"Error generating personalized playlists: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/delete_playlist', methods=['POST'])
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
def api_cover_art(playlist_name):
    """API endpoint to serve cover art for playlists"""
    try:
        from flask import send_file
        
        playlist_dir = Path(config.playlist_folder) / playlist_name
        cover_path = playlist_dir / 'cover.jpg'
        
        if cover_path.exists():
            return send_file(str(cover_path), mimetype='image/jpeg')
        else:
            # Return a default placeholder or 404
            return '', 404
            
    except Exception as e:
        logger.error(f"Error serving cover art for {playlist_name}: {e}")
        return '', 404

@app.route('/api/spotify/test', methods=['POST'])
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
def api_jellyfin_test():
    """Test Jellyfin connection"""
    jellyfin_api = JellyfinAPI(config, logger)
    connected = jellyfin_api.test_connection()
    return jsonify({'connected': connected})

@app.route('/api/metadata')
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

@app.route('/api/users')
def api_users():
    """Get all Jellyfin users"""
    try:
        jellyfin_api = JellyfinAPI(config, logger)
        users = jellyfin_api.get_users()
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/user_settings', methods=['GET'])
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
    """Get playlist statistics"""
    try:
        playlist_dir = Path(config.playlist_folder)
        if not playlist_dir.exists():
            return {'total': 0, 'genres': 0, 'years': 0, 'artists': 0, 'personal': 0}
        
        playlists = list(playlist_dir.iterdir())
        total = len(playlists)
        
        genres = len([p for p in playlists if 'Genre:' in p.name])
        years = len([p for p in playlists if 'Year:' in p.name])
        artists = len([p for p in playlists if 'Artist:' in p.name])
        personal = len([p for p in playlists if 'Personal:' in p.name])
        
        return {
            'total': total,
            'genres': genres,
            'years': years,
            'artists': artists,
            'personal': personal
        }
    except Exception as e:
        logger.error(f"Error getting playlist stats: {e}")
        return {'total': 0, 'genres': 0, 'years': 0, 'artists': 0, 'personal': 0}

def get_detailed_playlist_info():
    """Get detailed playlist information"""
    try:
        playlist_dir = Path(config.playlist_folder)
        if not playlist_dir.exists():
            return []
        
        playlists = []
        for playlist_path in playlist_dir.iterdir():
            if playlist_path.is_dir():
                xml_file = playlist_path / 'playlist.xml'
                if xml_file.exists():
                    # Get file stats
                    stat = xml_file.stat()
                    created = datetime.fromtimestamp(stat.st_ctime)
                    modified = datetime.fromtimestamp(stat.st_mtime)
                    
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
                    
                    playlists.append({
                        'name': playlist_path.name,
                        'track_count': track_count,
                        'created': created.strftime('%Y-%m-%d %H:%M:%S'),
                        'modified': modified.strftime('%Y-%m-%d %H:%M:%S'),
                        'size': xml_file.stat().st_size
                    })
        
        return sorted(playlists, key=lambda x: x['name'])
    except Exception as e:
        logger.error(f"Error getting playlist info: {e}")
        return []

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
