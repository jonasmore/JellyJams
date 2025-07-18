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
    """Settings page"""
    settings = config_manager.load_settings()
    
    # Get available genres, years, and artists from Jellyfin
    jellyfin_api = JellyfinAPI(config, logger)
    metadata = get_jellyfin_metadata(jellyfin_api)
    
    return render_template('settings.html', 
                         settings=settings,
                         available_genres=metadata['genres'],
                         available_years=metadata['years'],
                         available_artists=metadata['artists'])

@app.route('/playlists')
def playlists():
    """Playlist management page"""
    playlist_info = get_detailed_playlist_info()
    return render_template('playlists.html', playlists=playlist_info)

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

@app.route('/api/generate', methods=['POST'])
def api_generate():
    """API endpoint to trigger playlist generation"""
    try:
        generator = PlaylistGenerator(config, logger)
        generator.generate_playlists()
        return jsonify({'success': True, 'message': 'Playlist generation completed'})
    except Exception as e:
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

@app.route('/api/jellyfin_test')
def api_jellyfin_test():
    """Test Jellyfin connection"""
    jellyfin_api = JellyfinAPI(config, logger)
    connected = jellyfin_api.test_connection()
    return jsonify({'connected': connected})

@app.route('/api/metadata')
def api_metadata():
    """Get Jellyfin metadata"""
    jellyfin_api = JellyfinAPI(config, logger)
    metadata = get_jellyfin_metadata(jellyfin_api)
    return jsonify(metadata)

def get_playlist_stats():
    """Get playlist statistics"""
    try:
        playlist_dir = Path(config.playlist_folder)
        if not playlist_dir.exists():
            return {'total': 0, 'genres': 0, 'years': 0, 'artists': 0}
        
        playlists = list(playlist_dir.iterdir())
        total = len(playlists)
        
        genres = len([p for p in playlists if 'Genre:' in p.name])
        years = len([p for p in playlists if 'Year:' in p.name])
        artists = len([p for p in playlists if 'Artist:' in p.name])
        
        return {
            'total': total,
            'genres': genres,
            'years': years,
            'artists': artists
        }
    except Exception as e:
        logger.error(f"Error getting playlist stats: {e}")
        return {'total': 0, 'genres': 0, 'years': 0, 'artists': 0}

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
