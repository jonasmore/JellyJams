#!/usr/bin/env python3
"""
JellyJams - Jellyfin Playlist Generator
Generates music playlists using Jellyfin API and saves them as XML files
"""

import os
import sys
import time
import json
import logging
import requests
import schedule
import signal
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

# PIL/Pillow imports for custom cover art generation
try:
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance
    import numpy as np
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Configuration
class Config:
    def __init__(self):
        # Load environment variables first (as defaults)
        self.jellyfin_url = os.getenv('JELLYFIN_URL', 'http://jellyfin:8096')
        self.api_key = os.getenv('JELLYFIN_API_KEY', '')
        self.playlist_folder = os.getenv('PLAYLIST_FOLDER', '/app/playlists')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.generation_interval = int(os.getenv('GENERATION_INTERVAL', '24'))
        self.max_tracks_per_playlist = int(os.getenv('MAX_TRACKS_PER_PLAYLIST', '100'))
        self.min_tracks_per_playlist = int(os.getenv('MIN_TRACKS_PER_PLAYLIST', '5'))
        self.excluded_genres = os.getenv('EXCLUDED_GENRES', '').split(',') if os.getenv('EXCLUDED_GENRES') else []
        self.excluded_artists = os.getenv('EXCLUDED_ARTISTS', '').split(',') if os.getenv('EXCLUDED_ARTISTS') else []
        self.shuffle_tracks = os.getenv('SHUFFLE_TRACKS', 'true').lower() == 'true'
        self.playlist_types = os.getenv('PLAYLIST_TYPES', 'Genre,Year,Artist,Personal').split(',')
        
        # Playlist diversity settings
        self.min_artist_diversity = int(os.getenv('MIN_ARTIST_DIVERSITY', '5'))
        
        # Spotify API configuration (optional)
        self.spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID', '')
        self.spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET', '')
        self.spotify_cover_art_enabled = os.getenv('SPOTIFY_COVER_ART_ENABLED', 'false').lower() == 'true'
        
        # User configuration for personalized playlists
        self.personal_playlist_users = os.getenv('PERSONAL_PLAYLIST_USERS', 'all')
        self.personal_playlist_new_users_default = os.getenv('PERSONAL_PLAYLIST_NEW_USERS_DEFAULT', 'true').lower() == 'true'
        self.personal_playlist_min_user_tracks = int(os.getenv('PERSONAL_PLAYLIST_MIN_USER_TRACKS', '10'))
        
        # Discovery playlist diversity settings
        self.discovery_max_songs_per_album = int(os.getenv('DISCOVERY_MAX_SONGS_PER_ALBUM', '1'))
        self.discovery_max_songs_per_artist = int(os.getenv('DISCOVERY_MAX_SONGS_PER_ARTIST', '2'))
        
        # Artist playlist requirements
        self.min_albums_per_artist = int(os.getenv('MIN_ALBUMS_PER_ARTIST', '2'))
        
        # Decade playlist requirements
        self.min_albums_per_decade = int(os.getenv('MIN_ALBUMS_PER_DECADE', '3'))
        
        # Media library scan after playlist creation
        self.trigger_library_scan = os.getenv('TRIGGER_LIBRARY_SCAN', 'true').lower() == 'true'
        
        # Scheduling configuration
        self.auto_generate_on_startup = os.getenv('AUTO_GENERATE_ON_STARTUP', 'false').lower() == 'true'
        self.schedule_mode = os.getenv('SCHEDULE_MODE', 'manual')  # manual, daily, interval
        self.schedule_time = os.getenv('SCHEDULE_TIME', '00:00')  # Time for daily mode (HH:MM)
        
        # Genre grouping/mapping system
        self.genre_grouping_enabled = os.getenv('GENRE_GROUPING_ENABLED', 'true').lower() == 'true'
        self.genre_mappings = self._load_genre_mappings()
        
        # Load web UI settings if they exist (these override environment variables)
        self.load_web_ui_settings()
    
    def load_web_ui_settings(self):
        """Load settings from web UI JSON file - these take precedence over environment variables"""
        config_file = '/app/config/settings.json'
        try:
            if Path(config_file).exists():
                with open(config_file, 'r') as f:
                    web_settings = json.load(f)
                    
                # Apply web UI settings (override environment variables)
                if 'jellyfin_url' in web_settings:
                    self.jellyfin_url = web_settings['jellyfin_url']
                if 'max_tracks_per_playlist' in web_settings:
                    self.max_tracks_per_playlist = int(web_settings['max_tracks_per_playlist'])
                if 'min_tracks_per_playlist' in web_settings:
                    self.min_tracks_per_playlist = int(web_settings['min_tracks_per_playlist'])
                if 'excluded_genres' in web_settings:
                    self.excluded_genres = web_settings['excluded_genres'] if isinstance(web_settings['excluded_genres'], list) else web_settings['excluded_genres'].split(',')
                if 'excluded_artists' in web_settings:
                    self.excluded_artists = web_settings['excluded_artists'] if isinstance(web_settings['excluded_artists'], list) else web_settings['excluded_artists'].split(',')
                if 'shuffle_tracks' in web_settings:
                    self.shuffle_tracks = bool(web_settings['shuffle_tracks'])
                if 'playlist_types' in web_settings:
                    self.playlist_types = web_settings['playlist_types'] if isinstance(web_settings['playlist_types'], list) else web_settings['playlist_types'].split(',')
                if 'generation_interval' in web_settings:
                    self.generation_interval = int(web_settings['generation_interval'])
                if 'log_level' in web_settings:
                    self.log_level = web_settings['log_level']
                if 'min_artist_diversity' in web_settings:
                    self.min_artist_diversity = int(web_settings['min_artist_diversity'])
                if 'spotify_client_id' in web_settings:
                    self.spotify_client_id = web_settings['spotify_client_id']
                if 'spotify_client_secret' in web_settings:
                    self.spotify_client_secret = web_settings['spotify_client_secret']
                if 'spotify_cover_art_enabled' in web_settings:
                    self.spotify_cover_art_enabled = bool(web_settings['spotify_cover_art_enabled'])
                
                # User configuration for personalized playlists
                if 'personal_playlist_users' in web_settings:
                    self.personal_playlist_users = web_settings['personal_playlist_users']
                if 'personal_playlist_new_users_only' in web_settings:
                    self.personal_playlist_new_users_only = bool(web_settings['personal_playlist_new_users_only'])
                
                # Scheduling configuration
                if 'auto_generate_on_startup' in web_settings:
                    self.auto_generate_on_startup = bool(web_settings['auto_generate_on_startup'])
                if 'schedule_mode' in web_settings:
                    self.schedule_mode = web_settings['schedule_mode']
                if 'schedule_time' in web_settings:
                    self.schedule_time = web_settings['schedule_time']
                if 'personal_playlist_min_user_tracks' in web_settings:
                    self.personal_playlist_min_user_tracks = int(web_settings['personal_playlist_min_user_tracks'])
                if 'discovery_max_songs_per_album' in web_settings:
                    self.discovery_max_songs_per_album = int(web_settings['discovery_max_songs_per_album'])
                if 'discovery_max_songs_per_artist' in web_settings:
                    self.discovery_max_songs_per_artist = int(web_settings['discovery_max_songs_per_artist'])
                if 'min_albums_per_artist' in web_settings:
                    self.min_albums_per_artist = int(web_settings['min_albums_per_artist'])
                if 'min_albums_per_decade' in web_settings:
                    self.min_albums_per_decade = int(web_settings['min_albums_per_decade'])
                if 'trigger_library_scan' in web_settings:
                    self.trigger_library_scan = bool(web_settings['trigger_library_scan'])
                    
                print(f"🎵  JellyJams web UI settings loaded - overriding environment variables")
                print(f"   Max tracks: {self.max_tracks_per_playlist}, Min tracks: {self.min_tracks_per_playlist}")
                print(f"   Playlist types: {', '.join(self.playlist_types)}")
                print(f"   Excluded genres: {', '.join(self.excluded_genres) if self.excluded_genres else 'None'}")
            print(f"   Excluded artists: {', '.join(self.excluded_artists) if self.excluded_artists else 'None'}")
                
        except Exception as e:
            print(f"⚠️  Could not load web UI settings: {e}")
            print(f"   Using environment variables instead")
    
    def _load_genre_mappings(self):
        """Load comprehensive genre mapping system to consolidate similar genres"""
        return {
            # Rock and its many subgenres
            'Rock': [
                'Rock', 'Classic Rock', 'Hard Rock', 'Soft Rock', 'Arena Rock', 'Art Rock',
                'Alternative Rock', 'Indie Rock', 'Progressive Rock', 'Psychedelic Rock',
                'Blues Rock', 'Country Rock', 'Folk Rock', 'Garage Rock', 'Glam Rock',
                'Gothic Rock', 'Grunge', 'Heartland Rock', 'Mainstream Rock', 'Math Rock',
                'Noise Rock', 'Post-Rock', 'Punk Rock', 'Southern Rock', 'Stoner Rock',
                'Symphonic Rock', 'Experimental Rock', 'Electronic Rock', 'Funk Rock',
                'Piano Rock', 'Garage Rock Revival', 'Desert Rock', 'Boogie Rock',
                'Swamp Rock', 'Roots Rock', 'Dance-Rock', 'Rap Rock', 'Nu Metal',
                'Acoustic Rock', 'AlternRock', 'Britpop', 'Crossover Prog', 'Indie Rock/Rock Pop',
                'Post-Grunge', 'Post-Britpop', 'Slacker Rock', 'Surf Punk', 'Beat Music'
            ],
            
            # Pop and its variants
            'Pop': [
                'Pop', 'Pop Rock', 'Dance-Pop', 'Electropop', 'Synth-Pop', 'Art Pop',
                'Alternative Pop', 'Indie Pop', 'Dream Pop', 'Power Pop', 'Baroque Pop',
                'Chamber Pop', 'Sunshine Pop', 'Traditional Pop', 'International Pop',
                'Ambient Pop', 'Bedroom Pop', 'Hypnagogic Pop', 'Jangle Pop', 'Noise Pop',
                'Twee Pop', 'Progressive Pop', 'Psychedelic Pop', 'Sophisti-Pop',
                'Indie Pop/Folk', 'Pop Soul', 'Pop Metal', 'Country Pop', 'Latin Pop',
                'J-Pop', 'Pop Punk', 'Pop Rap', 'Reggae-Pop'
            ],
            
            # Electronic and dance music
            'Electronic': [
                'Electronic', 'Electronica', 'Electro', 'EDM', 'Techno', 'House',
                'Trance', 'Dubstep', 'Drum And Bass', 'Ambient', 'Downtempo',
                'Breakbeat', 'Breaks', 'Big Beat', 'Dance', 'Electro House',
                'Deep House', 'Tech House', 'Progressive House', 'Hard Techno',
                'Hardstyle', 'Dark Electro', 'Electro-Industrial', 'Trip Hop',
                'Chillwave', 'Synthwave', 'Minimal Synth', 'Indietronica',
                'Folktronica', 'New Rave', 'Jersey Club', 'Leftfield'
            ],
            
            # Hip Hop and Rap
            'Hip Hop': [
                'Hip Hop', 'Rap/Hip Hop', 'Alternative Hip Hop', 'East Coast Hip Hop',
                'Southern Hip Hop', 'Conscious Hip Hop', 'Political Hip Hop',
                'Experimental Hip Hop', 'Cloud Rap', 'Emo Rap', 'Trap', 'Grime',
                'Hip House', 'Rap Metal', 'Rapcore', 'Country Rap', 'Trap Latino',
                'Sexy Drill'
            ],
            
            # Alternative and Indie
            'Alternative': [
                'Alternative', 'Alternative Country', 'Alternative Dance', 'Alternative Folk',
                'Alternative Hip Hop', 'Alternative Metal', 'Alternative Pop', 'Alternative Punk',
                'Alternative R&B', 'Indie Folk', 'Indie Pop', 'Indie Rock', 'Indie Surf',
                'Indie, Blues Rock', 'Neo-Acoustic', 'Neo-Psychedelia'
            ],
            
            # Metal
            'Metal': [
                'Metal', 'Heavy Metal', 'Alternative Metal', 'Doom Metal', 'Glam Metal',
                'Gothic Metal', 'Industrial Metal', 'Nu Metal', 'Pop Metal',
                'Progressive Metal', 'Rap Metal', 'Stoner Metal', 'Traditional Doom Metal',
                'Neue Deutsche HäRte'
            ],
            
            # Punk
            'Punk': [
                'Punk', 'Punk Rock', 'Alternative Punk', 'Dance-Punk', 'Garage Punk',
                'Pop Punk', 'Post-Punk', 'Post-Punk Revival', 'Punk Blues', 'Surf Punk',
                'Emo', 'Hardcore', 'Melodic Hardcore', 'Post-Hardcore', 'Midwest Emo'
            ],
            
            # Blues
            'Blues': [
                'Blues', 'Blues Rock', 'British Blues', 'Country Blues', 'Electric Blues',
                'Hill Country Blues', 'Piano Blues', 'Punk Blues', 'Blue-Eyed Soul'
            ],
            
            # Jazz
            'Jazz': [
                'Jazz', 'Jazz Fusion', 'Vocal Jazz', 'Dixieland'
            ],
            
            # Country
            'Country': [
                'Country', 'Alternative Country', 'Country Blues', 'Country Pop',
                'Country Rap', 'Country Rock', 'Country Soul', 'Progressive Country',
                'Traditional Country', 'Americana'
            ],
            
            # R&B and Soul
            'R&B': [
                'R&B', 'Contemporary R&B', 'Alternative R&B', 'Soul', 'Neo Soul',
                'Pop Soul', 'Psychedelic Soul', 'Southern Soul', 'Smooth Soul',
                'Country Soul', 'Blue-Eyed Soul'
            ],
            
            # Funk
            'Funk': [
                'Funk', 'Funk Rock', 'Synth Funk'
            ],
            
            # Reggae
            'Reggae': [
                'Reggae', 'Reggae-Pop', 'Reggaeton', 'Dancehall', 'Dub', 'Ambient Dub'
            ],
            
            # Folk
            'Folk': [
                'Folk', 'Alternative Folk', 'Contemporary Folk', 'Folk Pop', 'Folk Rock',
                'Indie Folk', 'Stomp And Holler'
            ],
            
            # Classical and Orchestral
            'Classical': [
                'Classical', 'Modern Classical', 'Cinematic Classical', 'Opera',
                'Orchestral', 'Symphonic Prog', 'Symphonic Rock'
            ],
            
            # World Music
            'World': [
                'Asian Music', 'Brazilian Music', 'Latin Music', 'Afrobeat', 'Soukous',
                'Salsa', 'Plena', 'Schlager'
            ],
            
            # Gospel and Religious
            'Gospel': [
                'Gospel', 'Contemporary Gospel', 'Southern Gospel'
            ],
            
            # Ambient and Experimental
            'Ambient': [
                'Ambient', 'Ambient Dub', 'Ambient Pop', 'Space Ambient', 'Experimental',
                'Avant-Garde', 'Noise Pop', 'Noise Rock', 'Slowcore'
            ],
            
            # Singer-Songwriter
            'Singer-Songwriter': [
                'Singer-Songwriter', 'Singer & Songwriter'
            ],
            
            # New Wave and Synth
            'New Wave': [
                'New Wave', 'New Romantic', 'Synth-Pop', 'Electropop', 'Synthwave',
                'Minimal Synth'
            ],
            
            # Disco
            'Disco': [
                'Disco'
            ],
            
            # Rockabilly
            'Rockabilly': [
                'Rockabilly', 'Rock And Roll', 'Rock & Roll/Rockabilly'
            ],
            
            # Industrial
            'Industrial': [
                'Industrial', 'Industrial Metal', 'Industrial Rock', 'Electro-Industrial'
            ],
            
            # Shoegaze
            'Shoegaze': [
                'Shoegaze', 'Dream Pop'
            ],
            
            # Lounge
            'Lounge': [
                'Lounge'
            ]
        }
    
    def map_genre_to_group(self, genre):
        """Map a specific genre to its broader group category"""
        if not self.genre_grouping_enabled:
            return genre
        
        # Clean up the genre name
        genre = genre.strip()
        
        # Search through mappings to find which group this genre belongs to
        for group_name, genre_list in self.genre_mappings.items():
            if genre in genre_list:
                return group_name
        
        # If no mapping found, return original genre
        return genre

class SpotifyClient:
    """Spotify API client for downloading cover art"""
    
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
        self.spotify = None
        # Statistics tracking
        self.stats = {
            'total_attempts': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'successful_searches': 0,
            'api_errors': 0,
            'response_times': [],
            'last_test_time': None,
            'last_test_result': False,
            'initialization_success': False,
            'initialization_attempts': 0
        }
        self._initialize_client()
    
    def _initialize_client(self):
        self.stats['initialization_attempts'] += 1
        
        if not self.config.spotify_cover_art_enabled:
            self.logger.info("Spotify cover art is disabled in configuration")
            return
            
        if not self.config.spotify_client_id or not self.config.spotify_client_secret:
            self.logger.warning("Spotify credentials not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")
            return
            
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyClientCredentials
            
            self.logger.info("Initializing Spotify API client...")
            client_credentials_manager = SpotifyClientCredentials(
                client_id=self.config.spotify_client_id,
                client_secret=self.config.spotify_client_secret
            )
            self.spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
            
            # Test the connection immediately
            try:
                # Simple test query to verify credentials work
                test_result = self.spotify.search(q='test', type='track', limit=1)
                self.logger.info("✅ Spotify API client initialized and tested successfully")
                self.stats['initialization_success'] = True
            except Exception as test_e:
                self.logger.error(f"❌ Spotify API credentials test failed: {test_e}")
                self.spotify = None
                self.stats['initialization_success'] = False
                self.stats['api_errors'] += 1
                
        except ImportError:
            self.logger.error("❌ Spotipy library not found. Install with: pip install spotipy")
            self.stats['initialization_success'] = False
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Spotify API client: {e}")
            self.spotify = None
            self.stats['initialization_success'] = False
            self.stats['api_errors'] += 1
    
    def is_enabled(self) -> bool:
        """Check if Spotify integration is enabled and configured"""
        return self.spotify is not None
    
    def search_artist_playlist(self, artist_name: str) -> dict:
        """Search for 'This is {artist}' playlist on Spotify"""
        # Double-check that Spotify client is available
        if not self.is_enabled() or self.spotify is None:
            self.logger.debug(f"Spotify client not available for searching artist: {artist_name}")
            return None
            
        try:
            # Search for "This is {artist}" playlist
            query = f"This is {artist_name}"
            self.logger.debug(f"Searching Spotify for: {query}")
            
            results = self.spotify.search(q=query, type='playlist', limit=10)
            
            # Validate results structure
            if not results or 'playlists' not in results or not results['playlists']:
                self.logger.debug(f"No playlists section in Spotify results for: {artist_name}")
                return None
                
            if 'items' not in results['playlists'] or not results['playlists']['items']:
                self.logger.debug(f"No playlist items found for: {artist_name}")
                return None
            
            # Look for exact or close matches
            for playlist in results['playlists']['items']:
                if not playlist or 'name' not in playlist:
                    continue
                    
                playlist_name = playlist['name'].lower()
                target_name = f"this is {artist_name.lower()}"
                
                # Check for exact match or close variations
                if (playlist_name == target_name or 
                    playlist_name == f"this is {artist_name.lower()}!" or
                    playlist_name.startswith(target_name)):
                    
                    self.logger.info(f"✅ Found Spotify playlist: {playlist['name']} for artist: {artist_name}")
                    self.stats['successful_searches'] += 1
                    return playlist
            
            self.logger.debug(f"No 'This is {artist_name}' playlist found on Spotify")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error searching Spotify for artist {artist_name}: {e}")
            self.stats['api_errors'] += 1
            return None
    
    def download_cover_art(self, playlist_info: dict, save_path: str) -> bool:
        """Download cover art from Spotify playlist"""
        if not playlist_info or not playlist_info.get('images'):
            return False
            
        try:
            # Get the highest quality image (first in the list)
            image_url = playlist_info['images'][0]['url']
            
            # Download the image
            import requests
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # Save to file
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            self.logger.info(f"Downloaded Spotify cover art: {save_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error downloading cover art: {e}")
            return False
    
    def get_artist_cover_art(self, artist_name: str, playlist_dir: Path) -> bool:
        """Get and save cover art for an artist playlist"""
        # Double-check that Spotify client is available
        if not self.is_enabled() or self.spotify is None:
            self.logger.debug(f"Spotify client not available for getting cover art for: {artist_name}")
            return False
            
        import time
        start_time = time.time()
        self.stats['total_attempts'] += 1
        
        try:
            # Check if cover art already exists
            cover_path = playlist_dir / 'cover.jpg'
            if cover_path.exists():
                self.logger.debug(f"Cover art already exists for {artist_name}")
                self.stats['successful_downloads'] += 1
                return True
            
            # Search for Spotify playlist
            playlist_info = self.search_artist_playlist(artist_name)
            if not playlist_info:
                self.stats['failed_downloads'] += 1
                return False
            
            # Download cover art
            success = self.download_cover_art(playlist_info, str(cover_path))
            
            # Track statistics
            response_time = time.time() - start_time
            self.stats['response_times'].append(response_time)
            if len(self.stats['response_times']) > 100:  # Keep last 100 response times
                self.stats['response_times'] = self.stats['response_times'][-100:]
            
            if success:
                self.stats['successful_downloads'] += 1
            else:
                self.stats['failed_downloads'] += 1
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error getting cover art for {artist_name}: {e}")
            self.stats['failed_downloads'] += 1
            self.stats['api_errors'] += 1
            return False
    
    def test_connection(self) -> dict:
        """Test Spotify API connection and return results"""
        import time
        from datetime import datetime
        
        test_result = {
            'success': False,
            'message': '',
            'response_time': 0,
            'timestamp': datetime.now().isoformat()
        }
        
        start_time = time.time()
        
        try:
            if not self.config.spotify_client_id or not self.config.spotify_client_secret:
                test_result['message'] = 'Spotify credentials not configured'
                return test_result
            
            if not self.is_enabled():
                test_result['message'] = 'Spotify client not initialized'
                return test_result
            
            # Test API call - search for a popular playlist
            results = self.spotify.search(q='This is Drake', type='playlist', limit=1)
            
            test_result['response_time'] = time.time() - start_time
            
            if results and results.get('playlists') and results['playlists'].get('items'):
                test_result['success'] = True
                test_result['message'] = 'Spotify API connection successful'
            else:
                test_result['message'] = 'Spotify API returned empty results'
                
        except Exception as e:
            test_result['response_time'] = time.time() - start_time
            test_result['message'] = f'Spotify API error: {str(e)}'
            self.stats['api_errors'] += 1
        
        # Update test statistics
        self.stats['last_test_time'] = test_result['timestamp']
        self.stats['last_test_result'] = test_result['success']
        
        return test_result
    
    def get_statistics(self) -> dict:
        """Get current Spotify integration statistics"""
        stats = self.stats.copy()
        
        # Calculate additional metrics
        if stats['total_attempts'] > 0:
            stats['success_rate'] = (stats['successful_downloads'] / stats['total_attempts']) * 100
        else:
            stats['success_rate'] = 0
            
        if stats['response_times']:
            stats['avg_response_time'] = sum(stats['response_times']) / len(stats['response_times'])
            stats['min_response_time'] = min(stats['response_times'])
            stats['max_response_time'] = max(stats['response_times'])
        else:
            stats['avg_response_time'] = 0
            stats['min_response_time'] = 0
            stats['max_response_time'] = 0
            
        return stats

# Setup logging
def setup_logging(config: Config):
    """Setup logging configuration with timestamps - ensure all logs visible in Docker"""
    # Ensure log directory exists
    log_dir = Path('/app/logs')
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Log directory created/verified: {log_dir}")
    except Exception as e:
        print(f"⚠️ Could not create log directory {log_dir}: {e}")
    
    # Force DEBUG level for comprehensive logging
    log_level = logging.DEBUG
    print(f"🔧 Forcing DEBUG level logging for comprehensive output")
    
    # Create formatters with timestamps
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    # Configure root logger to catch ALL logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    
    # Console handler for Docker logs
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Also setup specific jellyjams logger
    logger = logging.getLogger('jellyjams')
    logger.setLevel(logging.DEBUG)
    logger.propagate = True  # Ensure it propagates to root logger
    
    # File handler (with error handling)
    try:
        file_handler = logging.FileHandler(log_dir / 'jellyjams.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        print(f"📝 File logging enabled: {log_dir / 'jellyjams.log'}")
    except Exception as e:
        print(f"⚠️ Could not create file handler: {e}")
        print("📺 Continuing with console logging only")
    
    # Disable other loggers that might interfere
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    print(f"🔧 Comprehensive logging initialized at DEBUG level with timestamps")
    print(f"📊 Root logger handlers: {len(root_logger.handlers)} ({[type(h).__name__ for h in root_logger.handlers]})")
    print(f"📊 JellyJams logger propagate: {logger.propagate}")
    
    # Test logging immediately
    logger.info("🎵 JellyJams logging system initialized and ready")
    logger.debug("🔍 Debug logging is active and visible")
    
    return logger

class JellyfinAPI:
    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update({
            'X-Emby-Token': config.api_key,
            'Content-Type': 'application/json'
        })

    def get_audio_items(self) -> List[Dict]:
        """Get all audio items from Jellyfin"""
        try:
            url = f"{self.config.jellyfin_url}/Items"
            params = {
                'IncludeItemTypes': 'Audio',
                'Recursive': 'true',
                'Fields': 'Path,Genres,ProductionYear,Artists,RunTimeTicks,DateCreated',
                'SortBy': 'SortName',
                'SortOrder': 'Ascending'
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('Items', [])
            
            self.logger.info(f"Retrieved {len(items)} audio items from Jellyfin")
            return items
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching audio items: {e}")
            return []

    def test_connection(self) -> bool:
        """Test connection to Jellyfin API"""
        try:
            url = f"{self.config.jellyfin_url}/System/Info"
            response = self.session.get(url)
            response.raise_for_status()
            
            info = response.json()
            self.logger.info(f"Connected to Jellyfin {info.get('Version', 'Unknown')} at {self.config.jellyfin_url}")
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to connect to Jellyfin: {e}")
            return False

    def get_users(self) -> List[Dict]:
        """Get all users from Jellyfin"""
        try:
            url = f"{self.config.jellyfin_url}/Users"
            response = self.session.get(url)
            response.raise_for_status()
            
            users = response.json()
            self.logger.info(f"Retrieved {len(users)} users from Jellyfin")
            return users
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching users: {e}")
            return []

    def get_user_listening_stats(self, user_id: str, limit: int = 100) -> List[Dict]:
        """Get user's most played tracks using Jellyfin's playback reporting"""
        try:
            # Try to get playback statistics from Jellyfin
            # Note: This requires the 'playback_reporting' plugin to be installed
            url = f"{self.config.jellyfin_url}/user_usage_stats/PlayActivity"
            params = {
                'user_id': user_id,
                'limit': limit,
                'media_type': 'Audio'
            }
            
            self.logger.debug(f"Attempting to get listening stats from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and data:
                    self.logger.info(f"✅ Retrieved {len(data)} listening stats for user {user_id}")
                    return data
                else:
                    self.logger.info(f"📊 Listening stats endpoint available but no data returned for user {user_id}")
                    return []
            elif response.status_code == 404:
                self.logger.info(f"📊 Playback reporting plugin not installed or endpoint not available (404)")
                return []
            else:
                self.logger.warning(f"📊 Playback reporting request failed (status: {response.status_code})")
                return []
                
        except requests.exceptions.Timeout:
            self.logger.warning(f"⏱️ Timeout getting listening stats for user {user_id}")
            return []
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"🌐 Network error getting listening stats for user {user_id}: {e}")
            return []
        except Exception as e:
            self.logger.warning(f"❌ Unexpected error getting listening stats for user {user_id}: {e}")
            return []

    def get_user_favorite_items(self, user_id: str) -> List[Dict]:
        """Get user's favorite/liked items"""
        try:
            url = f"{self.config.jellyfin_url}/Users/{user_id}/Items"
            params = {
                'IsFavorite': 'true',
                'IncludeItemTypes': 'Audio',
                'Recursive': 'true',
                'Fields': 'Path,Genres,ProductionYear,Artists,RunTimeTicks,DateCreated,UserData'
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('Items', [])
            self.logger.info(f"Retrieved {len(items)} favorite tracks for user {user_id}")
            return items
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching user favorites: {e}")
            return []

    def get_recently_played(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get user's recently played tracks"""
        try:
            url = f"{self.config.jellyfin_url}/Users/{user_id}/Items"
            params = {
                'IncludeItemTypes': 'Audio',
                'Recursive': 'true',
                'SortBy': 'DatePlayed',
                'SortOrder': 'Descending',
                'Limit': limit,
                'Fields': 'Path,Genres,ProductionYear,Artists,RunTimeTicks,DateCreated,UserData'
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('Items', [])
            # Filter only items that have been played
            played_items = [item for item in items if item.get('UserData', {}).get('LastPlayedDate')]
            self.logger.info(f"Retrieved {len(played_items)} recently played tracks for user {user_id}")
            return played_items
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching recently played: {e}")
            return []

    def get_similar_tracks_by_genre(self, reference_tracks: List[Dict], all_tracks: List[Dict], limit: int = 50) -> List[Dict]:
        """Find similar tracks based on genre matching"""
        if not reference_tracks:
            return []
        
        # Extract genres from reference tracks
        reference_genres = set()
        for track in reference_tracks:
            if track.get('Genres'):
                if isinstance(track['Genres'], list):
                    reference_genres.update(track['Genres'])
                elif isinstance(track['Genres'], str):
                    reference_genres.add(track['Genres'])
        
        # Find tracks with matching genres
        similar_tracks = []
        reference_ids = {track.get('Id') for track in reference_tracks}
        
        for track in all_tracks:
            # Skip if it's already in reference tracks
            if track.get('Id') in reference_ids:
                continue
                
            track_genres = set()
            if track.get('Genres'):
                if isinstance(track['Genres'], list):
                    track_genres.update(track['Genres'])
                elif isinstance(track['Genres'], str):
                    track_genres.add(track['Genres'])
            
            # Calculate genre overlap
            genre_overlap = len(reference_genres.intersection(track_genres))
            if genre_overlap > 0:
                track['similarity_score'] = genre_overlap / len(reference_genres)
                similar_tracks.append(track)
        
        # Sort by similarity score and return top matches
        similar_tracks.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
        return similar_tracks[:limit]

    def create_playlist(self, name: str, track_ids: List[str], user_id: str = None, is_public: bool = True) -> Dict:
        """Create a playlist using Jellyfin's REST API"""
        try:
            # If no user_id provided, get the first available user
            if not user_id:
                users = self.get_users()
                if not users:
                    raise Exception("No users found in Jellyfin")
                user_id = users[0]['Id']
                self.logger.info(f"Using user {users[0]['Name']} ({user_id}) for playlist creation")
            
            # Create the playlist
            url = f"{self.config.jellyfin_url}/Playlists"
            payload = {
                "Name": name,
                "IsPublic": is_public,
                "Ids": track_ids,
                "UserId": user_id
            }
            
            privacy_text = "public" if is_public else "private"
            self.logger.info(f"Creating {privacy_text} playlist '{name}' with {len(track_ids)} tracks for user {user_id}")
            
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            
            playlist_data = response.json()
            playlist_id = playlist_data.get('Id')
            
            self.logger.info(f"Successfully created {privacy_text} playlist '{name}' with ID: {playlist_id}")
            
            return {
                'success': True,
                'playlist_id': playlist_id,
                'name': name,
                'track_count': len(track_ids),
                'user_id': user_id,
                'is_public': is_public
            }
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error creating playlist '{name}': {e}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Response status: {e.response.status_code}")
                self.logger.error(f"Response text: {e.response.text}")
            return {
                'success': False,
                'error': str(e),
                'name': name
            }
        except Exception as e:
            self.logger.error(f"Unexpected error creating playlist '{name}': {e}")
            return {
                'success': False,
                'error': str(e),
                'name': name
            }

    def get_playlist_by_name(self, name: str, user_id: str = None) -> Dict:
        """Check if a playlist with the given name already exists"""
        try:
            if not user_id:
                users = self.get_users()
                if not users:
                    return None
                user_id = users[0]['Id']
            
            url = f"{self.config.jellyfin_url}/Users/{user_id}/Items"
            params = {
                'IncludeItemTypes': 'Playlist',
                'Recursive': 'true',
                'SearchTerm': name
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            playlists = data.get('Items', [])
            
            # Look for exact name match
            for playlist in playlists:
                if playlist.get('Name', '').lower() == name.lower():
                    return playlist
            
            return None
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error checking for existing playlist '{name}': {e}")
            return None

    def delete_playlist(self, playlist_id: str) -> bool:
        """Delete a playlist by ID"""
        try:
            url = f"{self.config.jellyfin_url}/Items/{playlist_id}"
            response = self.session.delete(url)
            response.raise_for_status()
            
            self.logger.info(f"Successfully deleted playlist with ID: {playlist_id}")
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error deleting playlist {playlist_id}: {e}")
            return False

    def trigger_library_scan(self) -> bool:
        """Trigger a media library scan in Jellyfin to refresh playlists"""
        try:
            url = f"{self.config.jellyfin_url}/Library/Refresh"
            response = self.session.post(url)
            response.raise_for_status()
            
            self.logger.info("Successfully triggered Jellyfin media library scan")
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error triggering library scan: {e}")
            return False

class PlaylistGenerator:
    def __init__(self, config: Config, logger):
        self.config = config
        self.logger = logger
        self.jellyfin = JellyfinAPI(config, logger)
        self.spotify = SpotifyClient(config, logger)
        # Add caching for API queries to prevent repeated expensive calls
        self._artist_path_cache = {}
        self._audio_items_cache = None
        self._cache_timestamp = None

    def _get_cached_audio_items(self) -> List[Dict]:
        """Get audio items with caching to prevent repeated expensive API calls"""
        import time
        current_time = time.time()
        
        # Cache for 30 minutes during cover art updates to prevent repeated API calls
        cache_duration = 1800  # 30 minutes for cover art operations
        
        if (self._audio_items_cache is None or 
            self._cache_timestamp is None or 
            current_time - self._cache_timestamp > cache_duration):
            
            self.logger.debug("📡 Fetching fresh audio items from Jellyfin API")
            self._audio_items_cache = self.jellyfin.get_audio_items()
            self._cache_timestamp = current_time
            self.logger.info(f"📋 Cached {len(self._audio_items_cache)} audio items for {cache_duration//60} minutes")
        else:
            self.logger.debug(f"📋 Using cached audio items ({len(self._audio_items_cache)} items, cached {int((current_time - self._cache_timestamp)/60)} minutes ago)")
        
        return self._audio_items_cache

    def copy_custom_cover_art(self, playlist_name: str, playlist_dir: Path) -> bool:
        """Copy custom cover art from /app/cover/ directory with fallback system and extension preservation"""
        try:
            # Define the source cover directory (matches Docker volume mount)
            cover_source_dir = Path("/app/cover")
            
            self.logger.info(f"Looking for custom cover art for playlist: {playlist_name}")
            self.logger.info(f"Checking cover source directory: {cover_source_dir}")
            
            if not cover_source_dir.exists():
                self.logger.warning(f"Cover source directory does not exist: {cover_source_dir}")
                return False
            
            # List all files in cover directory for debugging
            try:
                cover_files = list(cover_source_dir.glob("*"))
                self.logger.info(f"Found {len(cover_files)} files in cover directory: {[f.name for f in cover_files[:10]]}")  # Show first 10
            except Exception as e:
                self.logger.warning(f"Could not list cover directory contents: {e}")
            
            # Look for cover image with playlist name (try common extensions)
            extensions = ['.jpg', '.jpeg', '.png', '.webp', '.bmp']
            source_image = None
            found_extension = None
            
            # First, try exact playlist name match
            self.logger.info(f"Trying exact match for: {playlist_name}")
            for ext in extensions:
                potential_file = cover_source_dir / f"{playlist_name}{ext}"
                self.logger.debug(f"Checking: {potential_file}")
                if potential_file.exists():
                    source_image = potential_file
                    found_extension = ext
                    self.logger.info(f"Found exact match cover art: {potential_file}")
                    break
            
            # If no exact match, try fallback with playlist type + "all"
            if not source_image:
                self.logger.info(f"No exact match found, trying fallback patterns...")
                # Extract playlist type for fallback (e.g., "Top Tracks - all", "Discovery Mix - all")
                fallback_patterns = []
                
                if "Top Tracks -" in playlist_name:
                    fallback_patterns.append("Top Tracks - all")
                elif "Discovery Mix -" in playlist_name:
                    fallback_patterns.append("Discovery Mix - all")
                elif "Recent Favorites -" in playlist_name:
                    fallback_patterns.append("Recent Favorites - all")
                elif "Genre Mix -" in playlist_name:
                    fallback_patterns.append("Genre Mix - all")
                elif "This is" in playlist_name:
                    fallback_patterns.append("This is - all")
                elif "Radio" in playlist_name:
                    fallback_patterns.append("Radio - all")
                elif "Back to" in playlist_name:
                    fallback_patterns.append("Back to - all")
                
                self.logger.info(f"Trying fallback patterns: {fallback_patterns}")
                
                # Try fallback patterns
                for pattern in fallback_patterns:
                    for ext in extensions:
                        potential_file = cover_source_dir / f"{pattern}{ext}"
                        self.logger.debug(f"Checking fallback: {potential_file}")
                        if potential_file.exists():
                            source_image = potential_file
                            found_extension = ext
                            self.logger.info(f"Found fallback cover art: {potential_file}")
                            break
                    if source_image:
                        break
            
            if not source_image:
                self.logger.info(f"No custom cover art found for playlist: {playlist_name} (tried exact match and fallback)")
                # Try artist folder fallback for artist playlists
                if self._try_artist_folder_fallback(playlist_name, playlist_dir):
                    return True
                return False
            
            # Copy and rename to folder.[original_extension] in the playlist directory
            # Preserve the original extension but rename to "folder"
            destination_filename = f"folder{found_extension}"
            destination_image = playlist_dir / destination_filename
            
            self.logger.info(f"Copying cover art: {source_image} -> {destination_image}")
            
            import shutil
            shutil.copy2(source_image, destination_image)
            
            # Ensure cover art is world-readable on host mounts
            try:
                os.chmod(destination_image, 0o664)
            except Exception as chmod_err:
                self.logger.debug(f"chmod failed for {destination_image}: {chmod_err}")
            
            self.logger.info(f"Successfully copied custom cover art: {source_image} -> {destination_image}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error copying custom cover art for {playlist_name}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _apply_decade_cover_art(self, playlist_name: str, playlist_dir: Path) -> bool:
        """Apply decade-specific cover art for decade playlists with fallback system"""
        try:
            # Extract decade from playlist name (e.g., "Back to the 1980s" -> "1980s")
            if "Back to the" not in playlist_name:
                self.logger.warning(f"Invalid decade playlist name format: {playlist_name}")
                return False
            
            decade = playlist_name.replace("Back to the ", "").strip()
            self.logger.info(f"🗓️ Looking for decade-specific cover art for: {decade}")
            
            # Define the source cover directory
            cover_source_dir = Path("/app/cover")
            
            if not cover_source_dir.exists():
                self.logger.warning(f"Cover source directory does not exist: {cover_source_dir}")
                return False
            
            # Look for decade-specific cover art files in multiple naming formats
            decade_cover_files = [
                # Full playlist name format (e.g., "Back to the 1990s.jpg")
                f"{playlist_name}.jpg",
                f"{playlist_name}.jpeg",
                f"{playlist_name}.png",
                # Decade-only format (e.g., "1990s-cover.jpg")
                f"{decade}-cover.jpg",
                f"{decade}-cover.jpeg", 
                f"{decade}-cover.png"
            ]
            
            source_image = None
            for cover_file in decade_cover_files:
                potential_file = cover_source_dir / cover_file
                if potential_file.exists() and potential_file.is_file():
                    source_image = potential_file
                    self.logger.info(f"🖼️ Found decade cover art: {source_image}")
                    break
            
            # If no specific decade cover found, try fallback for pre-1900s music
            if not source_image and decade.endswith('s'):
                try:
                    decade_year = int(decade[:-1])  # Remove 's' and convert to int
                    if decade_year < 1900:
                        self.logger.info(f"🕰️ Decade {decade} is before 1900s, trying 1800s fallback...")
                        fallback_files = [
                            "1800s-cover.jpg",
                            "1800s-cover.jpeg",
                            "1800s-cover.png"
                        ]
                        
                        for fallback_file in fallback_files:
                            potential_fallback = cover_source_dir / fallback_file
                            if potential_fallback.exists() and potential_fallback.is_file():
                                source_image = potential_fallback
                                self.logger.info(f"🖼️ Found 1800s fallback cover art: {source_image}")
                                break
                except ValueError:
                    self.logger.warning(f"Could not parse decade year from: {decade}")
            
            if not source_image:
                self.logger.info(f"❌ No decade-specific cover art found for {decade}")
                return False
            
            # Determine destination filename (preserve original extension)
            source_extension = source_image.suffix
            destination_filename = f"cover{source_extension}"
            destination_image = playlist_dir / destination_filename
            
            self.logger.info(f"📋 Copying decade cover art: {source_image} -> {destination_image}")
            
            import shutil
            shutil.copy2(source_image, destination_image)
            
            # Ensure cover art is world-readable on host mounts
            try:
                os.chmod(destination_image, 0o664)
            except Exception as chmod_err:
                self.logger.debug(f"chmod failed for {destination_image}: {chmod_err}")
            
            self.logger.info(f"✅ Successfully applied decade cover art: {source_image} -> {destination_image}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error applying decade cover art for {playlist_name}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _apply_genre_cover_art(self, playlist_name: str, genre_name: str, playlist_dir: Path) -> bool:
        """Apply genre-specific cover art with hybrid predefined/generated approach"""
        try:
            self.logger.info(f"🎵 Looking for genre cover art for: {genre_name}")
            
            # Define the source cover directory
            cover_source_dir = Path("/app/cover")
            
            if not cover_source_dir.exists():
                self.logger.warning(f"Cover source directory does not exist: {cover_source_dir}")
                return False
            
            # First, try to find predefined genre cover art
            predefined_cover_files = [
                f"{genre_name} Radio.jpg",
                f"{genre_name} Radio.jpeg",
                f"{genre_name} Radio.png",
                f"{genre_name}.jpg",
                f"{genre_name}.jpeg",
                f"{genre_name}.png"
            ]
            
            source_image = None
            for cover_file in predefined_cover_files:
                potential_file = cover_source_dir / cover_file
                if potential_file.exists() and potential_file.is_file():
                    source_image = potential_file
                    self.logger.info(f"🖼️ Found predefined genre cover art: {source_image}")
                    break
            
            # If predefined cover found, copy it directly
            if source_image:
                source_extension = source_image.suffix
                destination_filename = f"cover{source_extension}"
                destination_image = playlist_dir / destination_filename
                
                self.logger.info(f"📋 Copying predefined genre cover art: {source_image} -> {destination_image}")
                
                import shutil
                shutil.copy2(source_image, destination_image)
                
                # Ensure cover art is world-readable on host mounts
                try:
                    os.chmod(destination_image, 0o664)
                except Exception as chmod_err:
                    self.logger.debug(f"chmod failed for {destination_image}: {chmod_err}")
                
                self.logger.info(f"✅ Successfully applied predefined genre cover art: {source_image} -> {destination_image}")
                return True
            
            # If no predefined cover found, generate one using "Fallback Radio.jpg" background
            self.logger.info(f"🎨 No predefined cover found, generating custom genre cover...")
            
            # Look for "Fallback Radio.jpg" background template
            background_files = [
                "Fallback Radio.jpg",
                "Fallback Radio.jpeg",
                "Fallback Radio.png"
            ]
            
            background_image = None
            for bg_file in background_files:
                potential_bg = cover_source_dir / bg_file
                if potential_bg.exists() and potential_bg.is_file():
                    background_image = potential_bg
                    self.logger.info(f"🖼️ Found background template: {background_image}")
                    break
            
            if not background_image:
                self.logger.warning(f"❌ No 'Fallback Radio.jpg' background template found for genre cover generation")
                return False
            
            # Generate custom genre cover with text overlay
            destination_image = playlist_dir / "cover.jpg"
            success = self._generate_genre_cover_art(background_image, genre_name, destination_image)
            
            if success:
                self.logger.info(f"✅ Successfully generated genre cover art for: {genre_name}")
                return True
            else:
                self.logger.warning(f"❌ Failed to generate genre cover art for: {genre_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error applying genre cover art for {playlist_name}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _generate_genre_cover_art(self, background_path: Path, genre_name: str, destination: Path) -> bool:
        """Generate genre cover art with centered text overlay on background template"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            self.logger.info(f"🎨 Generating genre cover art: {genre_name} on {background_path}")
            
            # Open and resize background image to standard size
            with Image.open(background_path) as background:
                # Convert to RGB if necessary
                if background.mode != 'RGB':
                    background = background.convert('RGB')
                
                # Resize to standard cover art size
                cover_size = (600, 600)
                background = background.resize(cover_size, Image.Resampling.LANCZOS)
                
                # Create drawing context
                draw = ImageDraw.Draw(background)
                
                # Try to load a bold font, fallback to default
                try:
                    # Try to find a system font
                    font_size = 400  # 5x bigger than original 80
                    font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", font_size)
                except:
                    try:
                        # Alternative system font paths
                        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
                    except:
                        # Fallback to default font
                        font = ImageFont.load_default()
                        self.logger.warning("Using default font for genre cover art")
                
                # Prepare text lines
                line1 = genre_name.upper()
                line2 = "RADIO"
                
                # Get text dimensions for centering
                bbox1 = draw.textbbox((0, 0), line1, font=font)
                bbox2 = draw.textbbox((0, 0), line2, font=font)
                
                text1_width = bbox1[2] - bbox1[0]
                text1_height = bbox1[3] - bbox1[1]
                text2_width = bbox2[2] - bbox2[0]
                text2_height = bbox2[3] - bbox2[1]
                
                # Calculate centered positions
                img_width, img_height = cover_size
                
                # Position text in center with some spacing between lines
                line_spacing = 20
                total_text_height = text1_height + text2_height + line_spacing
                
                y_start = (img_height - total_text_height) // 2
                
                x1 = (img_width - text1_width) // 2
                y1 = y_start
                
                x2 = (img_width - text2_width) // 2
                y2 = y_start + text1_height + line_spacing
                
                # Draw text with white color and black outline for visibility
                outline_width = 3
                text_color = "white"
                outline_color = "black"
                
                # Draw outline by drawing text in multiple positions
                for adj_x in range(-outline_width, outline_width + 1):
                    for adj_y in range(-outline_width, outline_width + 1):
                        if adj_x != 0 or adj_y != 0:
                            draw.text((x1 + adj_x, y1 + adj_y), line1, font=font, fill=outline_color)
                            draw.text((x2 + adj_x, y2 + adj_y), line2, font=font, fill=outline_color)
                
                # Draw main text
                draw.text((x1, y1), line1, font=font, fill=text_color)
                draw.text((x2, y2), line2, font=font, fill=text_color)
                
                # Save the final image
                background.save(destination, "JPEG", quality=95)
                
                self.logger.info(f"✅ Generated genre cover art: {destination}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error generating genre cover art: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _try_artist_folder_fallback(self, playlist_name: str, playlist_dir: Path) -> bool:
        """Generate custom cover art with 'This is <artist>' text overlay from artist folder images"""
        try:
            # Only apply this fallback for artist playlists
            if not playlist_name.startswith("This is "):
                return False
            
            # Extract artist name from playlist name ("This is Artist!" -> "Artist")
            artist_name = playlist_name.replace("This is ", "").rstrip("!")
            self.logger.info(f"Generating custom cover art for: {artist_name}")
            
            # Find artist folder and source image
            source_cover = self._find_artist_cover_image(artist_name)
            if not source_cover:
                return False
            
            # Generate custom cover art with text overlay
            destination_cover = playlist_dir / "folder.png"
            success = self._generate_custom_cover_art(source_cover, artist_name, destination_cover)
            
            if success:
                self.logger.info(f"✅ Successfully generated custom cover art: {destination_cover}")
                return True
            else:
                # Fallback to simple copy if text overlay fails
                self.logger.warning("Text overlay failed, falling back to simple copy")
                import shutil
                file_extension = source_cover.suffix
                fallback_destination = playlist_dir / f"folder{file_extension}"
                shutil.copy2(source_cover, fallback_destination)
                
                # Ensure cover art is world-readable on host mounts
                try:
                    os.chmod(fallback_destination, 0o664)
                except Exception as chmod_err:
                    self.logger.debug(f"chmod failed for {fallback_destination}: {chmod_err}")
                
                self.logger.info(f"✅ Fallback: copied artist folder cover art: {fallback_destination}")
                return True
            
        except Exception as e:
            self.logger.error(f"❌ Error in artist folder fallback for {playlist_name}: {e}")
            import traceback
            self.logger.debug(f"Full traceback: {traceback.format_exc()}")
            return False
    
    def _find_artist_cover_image(self, artist_name: str) -> Path:
        """Find cover image in artist folder using Jellyfin API and common paths"""
        self.logger.debug(f"🔍 Searching for artist folder: {artist_name}")
        
        # First try to get artist info from Jellyfin API
        artist_path = self._get_artist_path_from_jellyfin(artist_name)
        if artist_path:
            self.logger.debug(f"📡 Got artist path from Jellyfin API: {artist_path}")
            cover_image = self._find_cover_in_directory(artist_path)
            if cover_image:
                return cover_image
        
        # Fallback to common paths including Unraid structure
        possible_base_paths = [
            Path("/mnt/user/media/data/music"),  # Unraid music path
            Path("/app/music"),  # Common Docker mount point
            Path("/music"),      # Alternative mount point
            Path("/media"),      # Another common mount
            Path("/data/music"), # Data directory mount
            Path("/mnt/music"),  # Mount point variant
            Path("/jellyfin/music"), # Jellyfin specific
        ]
        
        # Debug: Show which paths exist
        self.logger.debug(f"📁 Checking base paths for artist folders:")
        for base_path in possible_base_paths:
            exists = base_path.exists()
            self.logger.debug(f"  {base_path}: {'✅ exists' if exists else '❌ not found'}")
            if exists:
                try:
                    # Show first few directories as examples
                    dirs = [d.name for d in base_path.iterdir() if d.is_dir()][:5]
                    self.logger.debug(f"    Sample directories: {dirs}")
                except Exception as e:
                    self.logger.debug(f"    Cannot list directories: {e}")
        
        # Try to find artist folder in various locations
        artist_folder = None
        for base_path in possible_base_paths:
            if not base_path.exists():
                continue
                
            self.logger.debug(f"🔍 Searching in: {base_path}")
            
            # Try direct artist folder
            potential_artist_folder = base_path / artist_name
            self.logger.debug(f"  Trying exact match: {potential_artist_folder}")
            if potential_artist_folder.exists() and potential_artist_folder.is_dir():
                artist_folder = potential_artist_folder
                self.logger.debug(f"  ✅ Found exact match!")
                break
            
            # Try to find artist folder with case-insensitive search
            try:
                self.logger.debug(f"  Trying case-insensitive search...")
                found_dirs = []
                for item in base_path.iterdir():
                    if item.is_dir():
                        found_dirs.append(item.name)
                        if item.name.lower() == artist_name.lower():
                            artist_folder = item
                            self.logger.debug(f"  ✅ Found case-insensitive match: {item}")
                            break
                
                if not artist_folder:
                    # Show some directories for debugging
                    sample_dirs = found_dirs[:10]
                    self.logger.debug(f"  No match found. Sample directories: {sample_dirs}")
                
                if artist_folder:
                    break
            except Exception as e:
                self.logger.debug(f"  Error searching {base_path}: {e}")
                continue
        
        if not artist_folder:
            self.logger.debug(f"❌ No artist folder found for: {artist_name}")
            return None
        
        self.logger.info(f"Found artist folder: {artist_folder}")
        
        # Look for folder.jpg or other cover art files in the artist folder
        cover_files = [
            "folder.jpg", "folder.jpeg", "folder.png",
            "cover.jpg", "cover.jpeg", "cover.png", 
            "artist.jpg", "artist.jpeg", "artist.png",
            "thumb.jpg", "thumb.jpeg", "thumb.png"
        ]
        
        for cover_file in cover_files:
            potential_cover = artist_folder / cover_file
            if potential_cover.exists() and potential_cover.is_file():
                self.logger.info(f"Found artist cover art: {potential_cover}")
                return potential_cover
        
        self.logger.debug(f"No cover art files found in artist folder: {artist_folder}")
        return None
    
    def _get_artist_path_from_jellyfin(self, artist_name: str) -> Path:
        """Get artist folder path from Jellyfin API with optimized caching"""
        try:
            # Check cache first to avoid repeated expensive API calls
            if artist_name in self._artist_path_cache:
                cached_result = self._artist_path_cache[artist_name]
                if cached_result is not None:
                    self.logger.debug(f"📋 Using cached path for artist: {artist_name} -> {cached_result}")
                else:
                    self.logger.debug(f"📋 Using cached negative result for artist: {artist_name}")
                return cached_result
            
            self.logger.debug(f"📡 Looking up artist path for: {artist_name}")
            
            # Get audio items from Jellyfin with caching - this should only happen once per session now
            audio_items = self._get_cached_audio_items()
            
            # Look for tracks by this artist and extract the path
            for item in audio_items:
                if 'Artists' in item and isinstance(item['Artists'], list):
                    for artist in item['Artists']:
                        if artist.lower() == artist_name.lower():
                            # Extract the directory path from the file path
                            file_path = item.get('Path')
                            if file_path:
                                # Get the parent directory (should be artist folder)
                                file_path_obj = Path(file_path)
                                # Go up directories to find artist folder
                                # Typical structure: /music/Artist/Album/Track.mp3
                                potential_artist_dir = file_path_obj.parent.parent
                                if potential_artist_dir.name.lower() == artist_name.lower():
                                    self.logger.debug(f"📁 Found artist directory from track path: {potential_artist_dir}")
                                    self._artist_path_cache[artist_name] = potential_artist_dir
                                    self.logger.debug(f"📡 Got artist path from Jellyfin API: {potential_artist_dir}")
                                    return potential_artist_dir
                                # Sometimes it might be: /music/Artist/Track.mp3
                                potential_artist_dir = file_path_obj.parent
                                if potential_artist_dir.name.lower() == artist_name.lower():
                                    self.logger.debug(f"📁 Found artist directory from track path: {potential_artist_dir}")
                                    self._artist_path_cache[artist_name] = potential_artist_dir
                                    self.logger.debug(f"📡 Got artist path from Jellyfin API: {potential_artist_dir}")
                                    return potential_artist_dir
        
            self.logger.debug(f"❌ No artist folder found for: {artist_name}")
            # Cache negative results too to prevent repeated failed lookups
            self._artist_path_cache[artist_name] = None
        
        except Exception as e:
            self.logger.debug(f"Error getting artist path from Jellyfin API: {e}")
            # Cache negative results for errors too
            self._artist_path_cache[artist_name] = None

        return None
    
    def _find_cover_in_directory(self, directory_path: Path) -> Path:
        """Find cover art files in a specific directory"""
        if not directory_path or not directory_path.exists():
            return None
        
        self.logger.debug(f"🔍 Searching for cover art in: {directory_path}")
        
        # Look for cover art files in the directory
        cover_files = [
            "folder.jpg", "folder.jpeg", "folder.png",
            "cover.jpg", "cover.jpeg", "cover.png", 
            "artist.jpg", "artist.jpeg", "artist.png",
            "thumb.jpg", "thumb.jpeg", "thumb.png"
        ]
        
        for cover_file in cover_files:
            potential_cover = directory_path / cover_file
            if potential_cover.exists() and potential_cover.is_file():
                self.logger.info(f"🖼️ Found cover art: {potential_cover}")
                return potential_cover
        
        self.logger.debug(f"No cover art files found in: {directory_path}")
        return None
    
    def _sanitize_text_for_font(self, text: str) -> str:
        """Sanitize text to handle Unicode characters that cause font encoding errors"""
        try:
            # Replace common Unicode characters that cause font issues
            replacements = {
                '\u2010': '-',  # Unicode hyphen → ASCII hyphen
                '\u2011': '-',  # Non-breaking hyphen → ASCII hyphen
                '\u2012': '-',  # Figure dash → ASCII hyphen
                '\u2013': '-',  # En dash → ASCII hyphen
                '\u2014': '-',  # Em dash → ASCII hyphen
                '\u2015': '-',  # Horizontal bar → ASCII hyphen
                '\u2018': "'", # Left single quotation mark → ASCII apostrophe
                '\u2019': "'", # Right single quotation mark → ASCII apostrophe
                '\u201C': '"',  # Left double quotation mark → ASCII quote
                '\u201D': '"',  # Right double quotation mark → ASCII quote
                '\u00A0': ' ',  # Non-breaking space → regular space
            }
            
            sanitized = text
            for unicode_char, replacement in replacements.items():
                sanitized = sanitized.replace(unicode_char, replacement)
            
            # Try to encode as latin-1 to catch any remaining problematic characters
            try:
                sanitized.encode('latin-1')
                return sanitized
            except UnicodeEncodeError:
                # If still problematic, remove non-ASCII characters
                sanitized = ''.join(char for char in sanitized if ord(char) < 128)
                self.logger.warning(f"Removed non-ASCII characters from artist name: {text} → {sanitized}")
                return sanitized
                
        except Exception as e:
            self.logger.warning(f"Error sanitizing text '{text}': {e}")
            # Fallback: remove all non-ASCII characters
            return ''.join(char for char in text if ord(char) < 128)
    
    def _generate_custom_cover_art(self, source_image: Path, artist_name: str, destination: Path) -> bool:
        """Generate custom cover art with 'This is <artist>' text overlay using multi-stage scaling approach"""
        try:
            import signal
            import time
            
            start_time = time.time()
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Cover art generation timed out")
            
            # Set timeout to prevent worker crashes - reduced to 10 seconds for faster processing
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(10)  # 10 second timeout
            
            # Open the source image
            with Image.open(source_image) as img:
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Create a copy to work with
                cover_img = img.copy()
                
                # Resize to smaller cover art size (350x350) for better text proportion
                cover_img.thumbnail((350, 350), Image.Resampling.LANCZOS)
                
                # Create a new 350x350 image with the resized image centered
                final_img = Image.new('RGB', (350, 350), (0, 0, 0))
                
                # Calculate position to center the image
                x = (350 - cover_img.width) // 2
                y = (350 - cover_img.height) // 2
                final_img.paste(cover_img, (x, y))
                
                # Create drawing context
                draw = ImageDraw.Draw(final_img)
                
                # Use extremely massive font size - 4x bigger again as requested (960pt)
                font_size = 960  # Extremely massive font size for 350x350 canvas to match reference
                font = None
                
                # Use a completely different approach - create large text by scaling
                # Start with a reasonable font size that we know works, then scale the image
                base_font_size = 80  # Use a size we know renders properly
                font = None
                
                # Try to load a system font at base size
                try:
                    # Try to find a system font
                    system_fonts = [
                        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',  # Linux
                        '/System/Library/Fonts/Helvetica.ttc',  # macOS
                        'arial.ttf',  # Windows fallback
                    ]
                    
                    for font_path in system_fonts:
                        try:
                            font = ImageFont.truetype(font_path, base_font_size)
                            self.logger.debug(f"Using system font: {font_path} at {base_font_size}pt")
                            break
                        except:
                            continue
                            
                except Exception as font_e:
                    self.logger.warning(f"Could not load system fonts: {font_e}")
                
                # If no system font, try default
                if font is None:
                    try:
                        font = ImageFont.load_default()
                        self.logger.debug(f"Using default font at base size")
                    except Exception:
                        self.logger.error("Could not load any font")
                        return False
                
                
                # Determine text color based on background brightness
                text_color = self._get_adaptive_text_color(final_img)
                
                # Define the text lines for "This is [Artist]" overlay
                line1 = "This is"
                # Sanitize artist name to handle Unicode characters that fonts can't render
                line2 = self._sanitize_text_for_font(artist_name)
                
                # Calculate text dimensions on large canvas
                if font:
                    bbox1 = draw.textbbox((0, 0), line1, font=font)
                    bbox2 = draw.textbbox((0, 0), line2, font=font)
                    
                    line1_width = bbox1[2] - bbox1[0]
                    line1_height = bbox1[3] - bbox1[1]
                    line2_width = bbox2[2] - bbox2[0]
                    line2_height = bbox2[3] - bbox2[1]
                    
                    max_width = max(line1_width, line2_width)
                    total_height = line1_height + line2_height + 5  # Minimum spacing between lines
                else:
                    # Fallback estimates
                    line1_height = 80
                    line2_height = 80
                    total_height = 200
                    max_width = 600
                
                # Create a large text canvas for high-quality text rendering
                text_canvas_size = 1000  # Large canvas for high-quality text
                text_img = Image.new('RGBA', (text_canvas_size, text_canvas_size), (0, 0, 0, 0))
                text_draw = ImageDraw.Draw(text_img)
                
                # Position text on large canvas (centered for now, we'll position the final result)
                text_x = 50  # Left margin on large canvas
                start_y = (text_canvas_size - total_height) // 2
                
                line1_y = start_y
                line2_y = start_y + line1_height + 5  # Minimum spacing between lines
                
                # Draw text on large canvas
                text_draw.text((text_x, line1_y), line1, fill=text_color, font=font)
                text_draw.text((text_x, line2_y), line2, fill=text_color, font=font)
                
                # Crop the text area to remove excess transparent space
                bbox = text_img.getbbox()
                if bbox:
                    text_img = text_img.crop(bbox)
                
                # Scale the text to be much larger - this is where we get the massive size
                scale_factor = 3.0  # Make text 3x larger
                new_width = int(text_img.width * scale_factor)
                new_height = int(text_img.height * scale_factor)
                text_img = text_img.resize((new_width, new_height), Image.LANCZOS)
                
                # Position the scaled text on the final image (bottom left)
                paste_x = 20  # Left margin
                paste_y = 350 - new_height - 30  # Bottom alignment with margin
                
                # Ensure text fits within image bounds
                if paste_y < 0:
                    paste_y = 10
                if paste_x + new_width > 350:
                    # Scale down if too wide
                    scale_factor = (350 - 40) / text_img.width
                    new_width = int(text_img.width * scale_factor)
                    new_height = int(text_img.height * scale_factor)
                    text_img = text_img.resize((new_width, new_height), Image.LANCZOS)
                    paste_y = 350 - new_height - 30
                
                # Paste the text onto the final image
                final_img.paste(text_img, (paste_x, paste_y), text_img)
                
                # Save the final image as PNG
                final_img.save(destination, 'PNG', quality=95)
                
                # Clear timeout
                signal.alarm(0)
                
                self.logger.info(f" Generated custom cover art with text overlay: {line1} {line2}")
                return True
                
        except ImportError:
            signal.alarm(0)  # Clear timeout
            self.logger.error("❌ Pillow library not available. Install with: pip install Pillow")
            return False
        except TimeoutError:
            signal.alarm(0)  # Clear timeout
            self.logger.error("❌ Cover art generation timed out after 30 seconds")
            return False
        except Exception as e:
            signal.alarm(0)  # Clear timeout
            self.logger.error(f"❌ Error generating custom cover art: {e}")
            import traceback
            self.logger.debug(f"Full traceback: {traceback.format_exc()}")
            return False
    
    def _get_adaptive_text_color(self, image: 'Image') -> tuple:
        """Determine text color (black or white) based on background brightness"""
        try:
            # Sample the bottom area where text will be placed
            bottom_area = image.crop((0, 480, 600, 600))  # Bottom 120px
            
            # Calculate average brightness
            import numpy as np
            img_array = np.array(bottom_area)
            
            # Calculate luminance using standard formula
            luminance = np.mean(img_array[:, :, 0] * 0.299 + 
                              img_array[:, :, 1] * 0.587 + 
                              img_array[:, :, 2] * 0.114)
            
            # Return white text for dark backgrounds, black for light backgrounds
            if luminance < 128:
                return (255, 255, 255)  # White text
            else:
                return (0, 0, 0)  # Black text
                
        except Exception as e:
            self.logger.debug(f"Error calculating adaptive text color: {e}")
            # Default to white text with shadow
            return (255, 255, 255)

    def _apply_discovery_diversity_controls(self, tracks: List[Dict]) -> List[Dict]:
        """Apply diversity controls to discovery playlist: limit songs per album and per artist"""
        try:
            album_counts = {}
            artist_counts = {}
            diverse_tracks = []
            
            self.logger.info(f"Applying diversity controls: max {self.config.discovery_max_songs_per_album} per album, {self.config.discovery_max_songs_per_artist} per artist")
            
            for track in tracks:
                # Get album and artist info
                album = track.get('Album', 'Unknown Album')
                artists = track.get('Artists', ['Unknown Artist'])
                
                # Check album limit
                if album_counts.get(album, 0) >= self.config.discovery_max_songs_per_album:
                    continue
                
                # Check artist limits for all artists on this track
                artist_limit_exceeded = False
                for artist in artists:
                    if artist_counts.get(artist, 0) >= self.config.discovery_max_songs_per_artist:
                        artist_limit_exceeded = True
                        break
                
                if artist_limit_exceeded:
                    continue
                
                # Track passes diversity checks, add it
                diverse_tracks.append(track)
                
                # Update counts
                album_counts[album] = album_counts.get(album, 0) + 1
                for artist in artists:
                    artist_counts[artist] = artist_counts.get(artist, 0) + 1
            
            self.logger.info(f"Diversity filtering: {len(tracks)} -> {len(diverse_tracks)} tracks (removed {len(tracks) - len(diverse_tracks)} for diversity)")
            return diverse_tracks
            
        except Exception as e:
            self.logger.error(f"Error applying diversity controls: {e}")
            return tracks  # Return original tracks if filtering fails

    def create_playlist_xml(self, playlist_name: str, tracks: List[Dict]) -> str:
        """Create playlist XML in Jellyfin format"""
        root = Element('Item')
        
        # Add metadata
        SubElement(root, 'Added').text = datetime.utcnow().strftime('%m/%d/%Y %H:%M:%S')
        SubElement(root, 'LockData').text = 'false'
        SubElement(root, 'LocalTitle').text = playlist_name
        
        # Calculate total runtime
        total_runtime = sum(track.get('RunTimeTicks', 0) for track in tracks)
        SubElement(root, 'RunningTime').text = str(total_runtime)
        
        # Get all unique genres
        all_genres = set()
        for track in tracks:
            if track.get('Genres'):
                # Parse genres - handle both list and semicolon-separated string formats
                if isinstance(track['Genres'], list):
                    for genre_item in track['Genres']:
                        if isinstance(genre_item, str) and ';' in genre_item:
                            # Split semicolon-separated genres
                            all_genres.update([g.strip() for g in genre_item.split(';') if g.strip()])
                        else:
                            all_genres.add(genre_item)
                elif isinstance(track['Genres'], str):
                    # Handle string format with semicolons
                    if ';' in track['Genres']:
                        all_genres.update([g.strip() for g in track['Genres'].split(';') if g.strip()])
                    else:
                        all_genres.add(track['Genres'])
        SubElement(root, 'Genres').text = '|'.join(sorted(all_genres))
        
        SubElement(root, 'PlaylistMediaType').text = 'Audio'
        
        # Add playlist items
        playlist_items = SubElement(root, 'PlaylistItems')
        for track in tracks:
            if track.get('Path'):
                playlist_item = SubElement(playlist_items, 'PlaylistItem')
                SubElement(playlist_item, 'Path').text = track['Path']
        
        # Add empty elements
        SubElement(root, 'Shares')
        SubElement(root, 'OwnerUserId').text = '00000000-0000-0000-0000-000000000000'
        
        # Format XML
        rough_string = tostring(root, 'unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent='  ')

    def _sanitize_playlist_name(self, name: str) -> str:
        """Sanitize playlist name to remove problematic characters"""
        if not name:
            return "Unknown Playlist"
        
        # Log original name for debugging
        self.logger.debug(f"Original playlist name: {repr(name)}")
        
        # Remove null bytes and other problematic characters
        sanitized = name.replace('\x00', '').replace('\0', '')

        # Normalize different types of hyphens and dashes to a standard hyphen
        hyphen_variants = ['\u2010', '\u2011', '\u2012', '\u2013', '\u2014', '\u2015']
        for variant in hyphen_variants:
            sanitized = sanitized.replace(variant, '-')
        
        # Remove other control characters
        import re
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
        
        # Replace problematic filesystem characters
        problematic_chars = ['<', '>', ':', '"', '|', '?', '*', '/', '\\']
        for char in problematic_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Clean up multiple spaces and trim
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        # Ensure it's not empty after sanitization
        if not sanitized:
            sanitized = "Unknown Playlist"
        
        # Log sanitized name if it changed
        if sanitized != name:
            self.logger.info(f"🧹 Sanitized playlist name: '{name}' -> '{sanitized}'")
        
        return sanitized
    
    def save_playlist(self, playlist_type: str, name: str, tracks: List[Dict], user_id: str = None):
        """Save playlist using Jellyfin's REST API with proper privacy controls and custom cover art"""
        self.logger.info(f"=== STARTING PLAYLIST CREATION ===")
        self.logger.info(f"Playlist Type: {playlist_type}")
        self.logger.info(f"Original Playlist Name: {repr(name)}")
        
        # Sanitize the playlist name to prevent filesystem errors
        sanitized_name = self._sanitize_playlist_name(name)
        self.logger.info(f"Sanitized Playlist Name: {sanitized_name}")
        self.logger.info(f"Track Count: {len(tracks)}")
        self.logger.info(f"User ID: {user_id}")
        
        try:
            if not tracks:
                self.logger.warning(f"No tracks to save for playlist: {name}")
                return None
            
            # Extract track IDs from the track objects
            track_ids = []
            for track in tracks:
                track_id = track.get('Id')
                if track_id:
                    track_ids.append(track_id)
                else:
                    self.logger.warning(f"Track missing ID: {track.get('Name', 'Unknown')}")
            
            if not track_ids:
                self.logger.error(f"No valid track IDs found for playlist: {name}")
                return None
            
            self.logger.info(f"Extracted {len(track_ids)} valid track IDs")
            
            # Determine privacy settings based on playlist type
            # Personalized playlists are private, general playlists are public
            is_public = playlist_type.lower() != "personal"
            privacy_text = "public" if is_public else "private"
            
            self.logger.info(f"Creating {privacy_text} {playlist_type} playlist: {sanitized_name} with {len(track_ids)} tracks")
            
            # Check if playlist already exists and delete it (use original name for API calls)
            self.logger.info(f"Checking for existing playlist: {name}")
            existing_playlist = self.jellyfin.get_playlist_by_name(name, user_id)
            if existing_playlist:
                self.logger.info(f"Playlist '{name}' already exists, attempting to delete old version with ID: {existing_playlist.get('Id')}")
                delete_success = self.jellyfin.delete_playlist(existing_playlist['Id'])
                if delete_success:
                    self.logger.info(f"✅ Successfully deleted existing playlist")
                else:
                    self.logger.info(f"🔄 Could not delete existing playlist (will create new version anyway)")
                    self.logger.debug(f"Note: Jellyfin may create a duplicate playlist or handle this automatically")
            else:
                self.logger.info(f"ℹ️ No existing playlist found with name: {name}")
        
            # Create the playlist via API with proper privacy settings (use original name for API)
            self.logger.info(f"🔨 Creating new playlist via Jellyfin API...")
            self.logger.debug(f"API call parameters: name={repr(name)}, track_count={len(track_ids)}, user_id={user_id}, is_public={is_public}")
            result = self.jellyfin.create_playlist(name, track_ids, user_id, is_public)
            
            if result['success']:
                self.logger.info(f"✅ Successfully created {privacy_text} playlist '{sanitized_name}' with {result['track_count']} tracks")
                
                # Create directory for cover art storage (use sanitized name for filesystem)
                self.logger.debug(f"Creating directory with sanitized name: {sanitized_name}")
                playlist_dir = Path(self.config.playlist_folder) / sanitized_name
                self.logger.debug(f"Full directory path: {playlist_dir}")
                
                try:
                    playlist_dir.mkdir(parents=True, exist_ok=True)
                    self.logger.info(f"📁 Created playlist directory: {playlist_dir}")
                except Exception as dir_error:
                    self.logger.error(f"❌ Error creating directory {playlist_dir}: {dir_error}")
                    self.logger.error(f"Directory path repr: {repr(str(playlist_dir))}")
                    raise
                
                # Handle cover art based on playlist type
                cover_added = False
                
                # For personalized playlists, try custom cover art first
                if playlist_type.lower() == "personal":
                    self.logger.info(f"Attempting to apply custom cover art for personalized playlist...")
                    cover_added = self.copy_custom_cover_art(name, playlist_dir)
                    if cover_added:
                        self.logger.info(f"✅ Applied custom cover art for personalized playlist: {name}")
                    else:
                        self.logger.info(f"No custom cover art found for personalized playlist: {name}")
                
                # For decade playlists, try decade-specific cover art
                elif playlist_type.lower() == "decade" and "Back to the" in name:
                    self.logger.info(f"🗓️ Attempting to apply decade-specific cover art...")
                    cover_added = self._apply_decade_cover_art(name, playlist_dir)
                    if cover_added:
                        self.logger.info(f"✅ Applied decade-specific cover art for playlist: {name}")
                    else:
                        self.logger.info(f"❌ No decade-specific cover art found for playlist: {name}")
                
                # For genre playlists, try genre-specific cover art
                elif playlist_type.lower() == "genre" and " Radio" in name:
                    # Extract genre name from "[Genre] Radio" format
                    genre_name = name.replace(" Radio", "").strip()
                    self.logger.info(f"🎵 Attempting to apply genre-specific cover art for: {genre_name}")
                    cover_added = self._apply_genre_cover_art(name, genre_name, playlist_dir)
                    if cover_added:
                        self.logger.info(f"✅ Applied genre-specific cover art for playlist: {name}")
                    else:
                        self.logger.info(f"❌ No genre-specific cover art found for playlist: {name}")
            
                # For artist playlists, try Spotify cover art first, then fallback to custom generation
                self.logger.debug(f"🔍 Cover art check - cover_added: {cover_added}, 'This is' in name: {'This is' in name}, spotify enabled: {self.spotify.is_enabled()}")
                self.logger.debug(f"🔍 Spotify client status: {self.spotify.spotify is not None}")
                
                if not cover_added and "This is" in name:
                    # Extract artist name from "This is [Artist]!" format
                    artist_name = name.replace("This is ", "").replace("!", "").strip()
                    self.logger.info(f"🎯 Extracted artist name: {artist_name}")
                    
                    # Try Spotify cover art first if enabled
                    if self.spotify.is_enabled():
                        self.logger.info(f"🎨 Attempting to apply Spotify cover art for artist playlist...")
                        if self.spotify.get_artist_cover_art(artist_name, playlist_dir):
                            cover_added = True
                            self.logger.info(f"✅ Applied Spotify cover art for artist playlist: {name}")
                        else:
                            self.logger.info(f"❌ No Spotify cover art found for artist: {artist_name}")
                    else:
                        self.logger.info(f"⚠️ Spotify cover art skipped - Spotify enabled: {self.spotify.is_enabled()}")
                        self.logger.info(f"🔧 Spotify client not enabled - client status: {self.spotify.spotify is not None}")
                    
                    # If Spotify didn't work (disabled or no cover found), try custom cover art generation
                    if not cover_added:
                        self.logger.info(f"🎨 Attempting custom cover art generation for artist: {artist_name}")
                        try:
                            # Always try to generate custom cover art with "This is [Artist]" text overlay
                            self.logger.info(f"🎨 Generating custom cover art for artist: {artist_name}")
                            
                            # First, find the source image to use as base
                            artist_cover_path = self._find_artist_cover_image(artist_name)
                            if artist_cover_path:
                                # Generate custom cover art with text overlay
                                cover_dest = playlist_dir / 'cover.jpg'
                                if self._generate_custom_cover_art(artist_cover_path, artist_name, cover_dest):
                                    cover_added = True
                                    self.logger.info(f"✅ Generated custom cover art for artist: {artist_name}")
                                else:
                                    self.logger.info(f"❌ Failed to generate custom cover art for artist: {artist_name}")
                                    # Fallback: copy the original image directly
                                    self.logger.info(f"🖼️ Fallback: Using original artist cover image: {artist_cover_path}")
                                    import shutil
                                    file_extension = artist_cover_path.suffix
                                    fallback_destination = playlist_dir / f"folder{file_extension}"
                                    shutil.copy2(artist_cover_path, fallback_destination)
                                    
                                    # Ensure cover art is world-readable on host mounts
                                    try:
                                        os.chmod(fallback_destination, 0o664)
                                    except Exception as chmod_err:
                                        self.logger.debug(f"chmod failed for {fallback_destination}: {chmod_err}")
                                    
                                    cover_added = True
                                    self.logger.info(f"✅ Applied existing artist cover art as fallback for: {artist_name}")
                            else:
                                self.logger.info(f"❌ No artist cover art found for: {artist_name}")
                        except Exception as cover_error:
                            self.logger.error(f"❌ Error generating custom cover art for {artist_name}: {cover_error}")
                
                if not cover_added:
                    self.logger.info(f"No cover art applied for playlist: {name}")
                
                self.logger.info(f"=== PLAYLIST CREATION COMPLETED SUCCESSFULLY ===")
                return playlist_dir
            else:
                self.logger.error(f"❌ Failed to create playlist '{name}': {result.get('error', 'Unknown error')}")
                self.logger.info(f"=== PLAYLIST CREATION FAILED ===")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error saving playlist {name}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.logger.info(f"=== PLAYLIST CREATION FAILED WITH EXCEPTION ===")
            return None

    def generate_genre_playlists(self, audio_items: List[Dict]):
        """Generate playlists by genre with genre grouping/mapping support"""
        self.logger.info("🎵 Generating genre-based playlists...")
        
        if self.config.genre_grouping_enabled:
            self.logger.info(f"🔄 Genre grouping enabled - consolidating {len(self.config.genre_mappings)} genre groups")
        else:
            self.logger.info("📋 Genre grouping disabled - using individual genres")
        
        # Group tracks by genre (with optional mapping to consolidated groups)
        genre_tracks = {}
        original_genre_stats = {}  # Track original genre distribution for logging
        
        for item in audio_items:
            if not item.get('Genres'):
                continue
            
            # Check if any artist in this track is excluded
            if self.config.excluded_artists and item.get('Artists'):
                excluded_artist_found = False
                for artist in item['Artists']:
                    if artist in self.config.excluded_artists:
                        excluded_artist_found = True
                        break
                if excluded_artist_found:
                    continue
            
            # Parse genres - handle both list and semicolon-separated string formats
            genres = []
            if isinstance(item['Genres'], list):
                for genre_item in item['Genres']:
                    if isinstance(genre_item, str) and ';' in genre_item:
                        # Split semicolon-separated genres
                        genres.extend([g.strip() for g in genre_item.split(';') if g.strip()])
                    elif isinstance(genre_item, str):
                        genres.append(genre_item.strip())
            elif isinstance(item['Genres'], str):
                if ';' in item['Genres']:
                    genres = [g.strip() for g in item['Genres'].split(';') if g.strip()]
                else:
                    genres = [item['Genres'].strip()]
            
            # Add track to each genre it belongs to (with optional mapping)
            for original_genre in genres:
                if original_genre and original_genre not in self.config.excluded_genres:
                    # Track original genre stats
                    original_genre_stats[original_genre] = original_genre_stats.get(original_genre, 0) + 1
                    
                    # Map to consolidated genre group if grouping is enabled
                    final_genre = self.config.map_genre_to_group(original_genre)
                    
                    if final_genre not in genre_tracks:
                        genre_tracks[final_genre] = []
                    genre_tracks[final_genre].append(item)
        
        # Create playlists for each genre
        for genre, tracks in genre_tracks.items():
            if len(tracks) < self.config.min_tracks_per_playlist:
                continue
            
            # Check artist diversity - count unique artists in this genre
            unique_artists = set()
            for track in tracks:
                if track.get('Artists'):
                    for artist in track['Artists']:
                        unique_artists.add(artist)
            
            if len(unique_artists) < self.config.min_artist_diversity:
                self.logger.info(f"Skipping genre '{genre}' - only {len(unique_artists)} artists (minimum: {self.config.min_artist_diversity})")
                continue
                
            # Limit tracks and shuffle if requested
            limited_tracks = tracks[:self.config.max_tracks_per_playlist]
            if self.config.shuffle_tracks:
                import random
                random.shuffle(limited_tracks)
            
            playlist_name = f"{genre} Radio"
            self.save_playlist("Genre", playlist_name, limited_tracks)
            self.logger.info(f"Created genre playlist '{playlist_name}' with {len(limited_tracks)} tracks from {len(unique_artists)} artists")

    def generate_year_playlists(self, audio_items: List[Dict]):
        """Generate playlists by decade (1980s, 1990s, 2000s, etc.)"""
        self.logger.info("🗓️ Generating decade-based playlists...")
        self.logger.info(f"Minimum albums required per decade: {self.config.min_albums_per_decade}")
        
        # Group tracks by decade and collect album data
        decade_data = {}
        for item in audio_items:
            year = item.get('ProductionYear')
            if not year or year < 1950:  # Skip very old or invalid years
                continue
            
            # Check if any artist in this track is excluded
            if self.config.excluded_artists and item.get('Artists'):
                excluded_artist_found = False
                for artist in item['Artists']:
                    if artist in self.config.excluded_artists:
                        excluded_artist_found = True
                        break
                if excluded_artist_found:
                    continue
            
            # Calculate decade (e.g., 1987 -> 1980s, 2003 -> 2000s)
            decade_start = (year // 10) * 10
            decade_name = f"{decade_start}s"
            
            if decade_name not in decade_data:
                decade_data[decade_name] = {
                    'tracks': [],
                    'albums': set(),
                    'artists': set()
                }
            
            decade_data[decade_name]['tracks'].append(item)
            
            # Track unique albums
            if item.get('Album'):
                decade_data[decade_name]['albums'].add(item['Album'])
            
            # Track unique artists
            if item.get('Artists'):
                for artist in item['Artists']:
                    decade_data[decade_name]['artists'].add(artist)
        
        # Create playlists for each decade with album threshold checking
        created_playlists = 0
        skipped_decades = []
        
        for decade, data in decade_data.items():
            tracks = data['tracks']
            unique_albums = data['albums']
            unique_artists = data['artists']
            
            # Check minimum track count
            if len(tracks) < self.config.min_tracks_per_playlist:
                self.logger.info(f"⏭️  Skipping decade '{decade}' - only {len(tracks)} tracks (minimum: {self.config.min_tracks_per_playlist})")
                skipped_decades.append(f"{decade} ({len(tracks)} tracks)")
                continue
            
            # Check minimum album count (NEW REQUIREMENT)
            if len(unique_albums) < self.config.min_albums_per_decade:
                self.logger.info(f"⏭️  Skipping decade '{decade}' - only {len(unique_albums)} albums (minimum: {self.config.min_albums_per_decade})")
                skipped_decades.append(f"{decade} ({len(unique_albums)} albums)")
                continue
            
            # Check artist diversity
            if len(unique_artists) < self.config.min_artist_diversity:
                self.logger.info(f"⏭️  Skipping decade '{decade}' - only {len(unique_artists)} artists (minimum: {self.config.min_artist_diversity})")
                skipped_decades.append(f"{decade} ({len(unique_artists)} artists)")
                continue
                
            # Limit tracks and shuffle if requested
            limited_tracks = tracks[:self.config.max_tracks_per_playlist]
            if self.config.shuffle_tracks:
                import random
                random.shuffle(limited_tracks)
            
            playlist_name = f"Back to the {decade}"
            self.save_playlist("Decade", playlist_name, limited_tracks)
            created_playlists += 1
            self.logger.info(f"✅ Created decade playlist '{playlist_name}' with {len(limited_tracks)} tracks from {len(unique_albums)} albums and {len(unique_artists)} artists")
        
        # Summary logging
        self.logger.info(f"🗓️ Decade playlist generation complete: {created_playlists} playlists created")
        if skipped_decades:
            self.logger.info(f"⏭️  Skipped {len(skipped_decades)} decades due to insufficient content: {', '.join(skipped_decades[:3])}{'...' if len(skipped_decades) > 3 else ''}")

    def generate_artist_playlists(self, audio_items: List[Dict]):
        """Generate playlists by artist with proper null-byte parsing"""
        self.logger.info("🎤 Generating artist-based playlists...")
        self.logger.info(f"Minimum albums required per artist: {self.config.min_albums_per_artist}")
        
        # Collect artist data with proper null-byte parsing
        self.logger.info("🎵 Collecting artist data...")
        artist_data = {}
        processed_items = 0
        
        for item in audio_items:
            processed_items += 1
            if processed_items % 100 == 0:
                self.logger.debug(f"📊 Processed {processed_items}/{len(audio_items)} audio items")
            
            # Parse null-byte-separated artist lists
            parsed_artists = []
            for artist in item['Artists']:
                if '\x00' in artist or '\0' in artist:
                    # Split on null bytes to get individual artists
                    individual_artists = [a.strip() for a in artist.replace('\0', '\x00').split('\x00') if a.strip()]
                    self.logger.debug(f"🎵 Parsed multi-artist field: {repr(artist)} -> {individual_artists}")
                    parsed_artists.extend(individual_artists)
                else:
                    parsed_artists.append(artist)
            
            # Update the item with parsed artists
            item['Artists'] = parsed_artists
            
            for artist in parsed_artists:
                if 'Old Mervs' in artist:
                    self.logger.info(f"[DEBUG] Found 'Old Mervs' during collection: {repr(artist)}")
                if artist not in artist_data:
                    artist_data[artist] = {'tracks': [], 'albums': set()}
                artist_data[artist]['tracks'].append(item)
                
                album = item.get('Album', 'Unknown Album')
                if album:
                    # Check for null bytes in album names too
                    if '\x00' in str(album) or '\0' in str(album):
                        self.logger.warning(f"⚠️ Found null byte in album name: {repr(album)}")
                        album = str(album).replace('\x00', '').replace('\0', '').strip()
                    artist_data[artist]['albums'].add(album)
        
        self.logger.info(f"📊 Processed {processed_items} audio items, found {len(artist_data)} unique artists")
        
        # Create playlists for each artist that meets requirements
        created_playlists = 0
        skipped_artists = []
        
        for artist, data in artist_data.items():
            tracks = data['tracks']
            album_count = len(data['albums'])
            
            # Debug logging for artist name
            self.logger.debug(f"Processing artist: {repr(artist)}")
            
            # Check if artist is excluded
            if self.config.excluded_artists and artist in self.config.excluded_artists:
                self.logger.info(f"⏭️  Skipping excluded artist: {artist}")
                skipped_artists.append(f"{artist} (excluded)")
                continue
            
            # Check minimum track requirement
            if len(tracks) < self.config.min_tracks_per_playlist:
                self.logger.debug(f"Skipping {artist}: only {len(tracks)} tracks (minimum: {self.config.min_tracks_per_playlist})")
                continue
            
            # Check minimum album requirement
            if album_count < self.config.min_albums_per_artist:
                self.logger.info(f"⏭️  Skipping {artist}: only {album_count} albums (minimum: {self.config.min_albums_per_artist})")
                skipped_artists.append(f"{artist} ({album_count} albums)")
                continue
            
            self.logger.info(f"✅ Creating playlist for {artist}: {len(tracks)} tracks from {album_count} albums")
            
            # Debug album information
            self.logger.debug(f"Albums for {artist}: {list(data['albums'])}")
            
            # Limit tracks and shuffle if requested
            limited_tracks = tracks[:self.config.max_tracks_per_playlist]
            if self.config.shuffle_tracks:
                import random
                random.shuffle(limited_tracks)
            
            # Create playlist name and log it for debugging
            playlist_name = f"This is {artist}!"
            if 'Old Mervs' in artist:
                self.logger.info(f"[DEBUG] Pre-sanitization name for 'Old Mervs': {repr(playlist_name)}")
            self.logger.debug(f"Generated playlist name: {repr(playlist_name)}")
            
            playlist_dir = self.save_playlist("Artist", playlist_name, limited_tracks)
            
            if playlist_dir:
                created_playlists += 1
                if 'Old Mervs' in artist:
                    self.logger.info(f"[DEBUG] Successfully saved playlist for 'Old Mervs' in directory: {playlist_dir}")
            elif 'Old Mervs' in artist:
                self.logger.error(f"[DEBUG] Failed to save playlist for 'Old Mervs'. `save_playlist` returned None.")
        
        # Summary logging
        self.logger.info(f"🎤 Artist playlist generation complete: {created_playlists} playlists created")
        if skipped_artists:
            self.logger.info(f"⏭️  Skipped {len(skipped_artists)} artists due to insufficient albums: {', '.join(skipped_artists[:5])}{'...' if len(skipped_artists) > 5 else ''}")
        
        if skipped_artists and len(skipped_artists) <= 10:
            self.logger.info(f"   Skipped artists: {', '.join(skipped_artists)}")
        elif len(skipped_artists) > 10:
            self.logger.info(f"   Skipped artists: {', '.join(skipped_artists[:10])} and {len(skipped_artists) - 10} more...")

    def _filter_users_for_personalized_playlists(self, users: List[Dict]) -> List[Dict]:
        """Filter users based on configuration settings for personalized playlists"""
        if self.config.personal_playlist_users == 'all':
            return users
        
        # Parse comma-separated list of usernames
        selected_usernames = [name.strip() for name in self.config.personal_playlist_users.split(',')]
        
        # Filter users by username
        filtered_users = []
        for user in users:
            user_name = user.get('Name', '')
            if user_name in selected_usernames:
                filtered_users.append(user)
                self.logger.info(f"User '{user_name}' selected for personalized playlists")
            else:
                self.logger.debug(f"User '{user_name}' not in selected list: {selected_usernames}")
        
        return filtered_users

    def generate_personalized_playlists(self, audio_items: List[Dict]):
        """Generate personalized playlists for selected users"""
        self.logger.info("Generating personalized playlists...")
        
        # Get all users
        users = self.jellyfin.get_users()
        if not users:
            self.logger.warning("No users found for personalized playlists")
            return
        
        # Filter users based on configuration
        selected_users = self._filter_users_for_personalized_playlists(users)
        if not selected_users:
            self.logger.info("No users selected for personalized playlist generation")
            return
        
        for user in selected_users:
            user_id = user.get('Id')
            user_name = user.get('Name', 'Unknown')
            
            if not user_id:
                continue
                
            self.logger.info(f"Generating personalized playlists for user: {user_name}")
            
            try:
                # Generate different types of personalized playlists
                self.generate_user_top_tracks_playlist(user_id, user_name, audio_items)
                self.generate_user_discovery_playlist(user_id, user_name, audio_items)
                self.generate_user_recent_favorites_playlist(user_id, user_name, audio_items)
                self.generate_user_genre_mix_playlist(user_id, user_name, audio_items)
                
            except Exception as e:
                self.logger.error(f"Error generating personalized playlists for {user_name}: {e}")

    def generate_user_top_tracks_playlist(self, user_id: str, user_name: str, audio_items: List[Dict]):
        """Generate a playlist of user's most played tracks"""
        try:
            self.logger.info(f"Generating top tracks playlist for {user_name}...")
            top_tracks = []
            
            # Try multiple methods to get user's top tracks
            # Method 1: Try to get listening stats (may not be available in all Jellyfin setups)
            try:
                listening_stats = self.jellyfin.get_user_listening_stats(user_id, limit=50)
                if listening_stats:
                    self.logger.info(f"Found {len(listening_stats)} listening stats for {user_name}")
                    # Extract track IDs from listening stats and find corresponding tracks
                    stats_track_ids = {stat.get('ItemId') for stat in listening_stats if stat.get('ItemId')}
                    
                    for track in audio_items:
                        if track.get('Id') in stats_track_ids:
                            # Add play count from stats
                            for stat in listening_stats:
                                if stat.get('ItemId') == track.get('Id'):
                                    track['play_count'] = stat.get('PlayCount', 0)
                                    break
                            top_tracks.append(track)
                    
                    # Sort by play count
                    top_tracks.sort(key=lambda x: x.get('play_count', 0), reverse=True)
                    self.logger.info(f"Using listening stats - found {len(top_tracks)} tracks with play counts")
                else:
                    self.logger.info(f"No listening stats returned for {user_name}")
            except Exception as stats_e:
                self.logger.warning(f"Could not get listening stats for {user_name}: {stats_e}")
            
            # Method 2: Fallback to favorite tracks if no listening stats available
            if not top_tracks:
                try:
                    self.logger.info(f"Falling back to favorite tracks for {user_name}")
                    favorite_tracks = self.jellyfin.get_user_favorite_items(user_id)
                    if favorite_tracks:
                        top_tracks = favorite_tracks
                        self.logger.info(f"Using favorites - found {len(top_tracks)} favorite tracks")
                    else:
                        self.logger.info(f"No favorite tracks found for {user_name}")
                except Exception as fav_e:
                    self.logger.warning(f"Could not get favorite tracks for {user_name}: {fav_e}")
            
            # Method 3: Final fallback to recently played tracks
            if not top_tracks:
                try:
                    self.logger.info(f"Final fallback to recently played tracks for {user_name}")
                    recent_tracks = self.jellyfin.get_recently_played(user_id, limit=30)
                    if recent_tracks:
                        top_tracks = recent_tracks
                        self.logger.info(f"Using recent tracks - found {len(top_tracks)} recently played tracks")
                    else:
                        self.logger.info(f"No recently played tracks found for {user_name}")
                except Exception as recent_e:
                    self.logger.warning(f"Could not get recently played tracks for {user_name}: {recent_e}")
            
            # Create playlist if we have tracks
            if top_tracks:
                # Ensure we have enough tracks for a meaningful playlist
                if len(top_tracks) < self.config.min_tracks_per_playlist:
                    self.logger.warning(f"Only {len(top_tracks)} tracks found for {user_name}, minimum is {self.config.min_tracks_per_playlist}")
                    return
                
                # Limit to configured max tracks
                limited_tracks = top_tracks[:self.config.max_tracks_per_playlist]
                if self.config.shuffle_tracks:
                    import random
                    random.shuffle(limited_tracks)
                
                playlist_name = f"Top Tracks - {user_name}"
                self.save_playlist("Personal", playlist_name, limited_tracks, user_id)
                self.logger.info(f"✅ Created top tracks playlist for {user_name} with {len(limited_tracks)} tracks")
            else:
                self.logger.warning(f"❌ No tracks found for {user_name} - cannot create top tracks playlist")
                
        except Exception as e:
            self.logger.error(f"❌ Error generating top tracks playlist for {user_name}: {e}")
            import traceback
            self.logger.debug(f"Full traceback: {traceback.format_exc()}")

    def generate_user_discovery_playlist(self, user_id: str, user_name: str, audio_items: List[Dict]):
        """Generate a discovery playlist with similar songs based on user's listening habits"""
        try:
            # Get user's recently played and favorite tracks
            recent_tracks = self.jellyfin.get_recently_played(user_id, limit=20)
            favorite_tracks = self.jellyfin.get_user_favorite_items(user_id)
            
            # Combine and deduplicate reference tracks
            reference_tracks = []
            seen_ids = set()
            
            for track_list in [recent_tracks, favorite_tracks]:
                for track in track_list:
                    track_id = track.get('Id')
                    if track_id and track_id not in seen_ids:
                        reference_tracks.append(track)
                        seen_ids.add(track_id)
            
            if reference_tracks:
                # Find similar tracks based on genres
                similar_tracks = self.jellyfin.get_similar_tracks_by_genre(
                    reference_tracks, audio_items, limit=self.config.max_tracks_per_playlist * 3
                )
                
                if similar_tracks:
                    # Apply diversity controls: max songs per album and per artist
                    diverse_tracks = self._apply_discovery_diversity_controls(similar_tracks)
                    
                    if self.config.shuffle_tracks:
                        import random
                        random.shuffle(diverse_tracks)
                    
                    # Limit to final playlist size
                    final_tracks = diverse_tracks[:self.config.max_tracks_per_playlist]
                    
                    playlist_name = f"Discovery Mix - {user_name}"
                    self.save_playlist("Personal", playlist_name, final_tracks, user_id)
                    self.logger.info(f"Created discovery playlist for {user_name} with {len(final_tracks)} tracks (applied diversity: max {self.config.discovery_max_songs_per_album} per album, {self.config.discovery_max_songs_per_artist} per artist)")
                else:
                    self.logger.info(f"No similar tracks found for {user_name}")
            else:
                self.logger.info(f"No reference tracks found for {user_name} discovery playlist")
                
        except Exception as e:
            self.logger.error(f"Error generating discovery playlist for {user_name}: {e}")

    def generate_user_recent_favorites_playlist(self, user_id: str, user_name: str, audio_items: List[Dict]):
        """Generate a playlist based on recently played tracks"""
        try:
            recent_tracks = self.jellyfin.get_recently_played(user_id, limit=30)
            
            if recent_tracks:
                # Limit to configured max tracks
                limited_tracks = recent_tracks[:self.config.max_tracks_per_playlist]
                if self.config.shuffle_tracks:
                    import random
                    random.shuffle(limited_tracks)
                
                playlist_name = f"Recent Favorites - {user_name}"
                self.save_playlist("Personal", playlist_name, limited_tracks, user_id)
                self.logger.info(f"Created recent favorites playlist for {user_name} with {len(limited_tracks)} tracks")
            else:
                self.logger.info(f"No recent tracks found for {user_name}")
                
        except Exception as e:
            self.logger.error(f"Error generating recent favorites playlist for {user_name}: {e}")

    def generate_user_genre_mix_playlist(self, user_id: str, user_name: str, audio_items: List[Dict]):
        """Generate a mixed playlist from user's favorite genres"""
        try:
            # Get user's favorite and recent tracks to determine preferred genres
            favorite_tracks = self.jellyfin.get_user_favorite_items(user_id)
            recent_tracks = self.jellyfin.get_recently_played(user_id, limit=20)
            
            # Combine reference tracks
            reference_tracks = favorite_tracks + recent_tracks
            
            if not reference_tracks:
                self.logger.info(f"No reference tracks found for {user_name} genre mix")
                return
            
            # Extract and count genres from user's listening history
            genre_counts = {}
            for track in reference_tracks:
                if track.get('Genres'):
                    track_genres = track['Genres'] if isinstance(track['Genres'], list) else [track['Genres']]
                    for genre in track_genres:
                        if isinstance(genre, str):
                            genre_counts[genre] = genre_counts.get(genre, 0) + 1
            
            # Get top 3 user genres
            top_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            
            if not top_genres:
                self.logger.info(f"No genres found for {user_name}")
                return
            
            # Find tracks from user's top genres
            genre_mix_tracks = []
            tracks_per_genre = self.config.max_tracks_per_playlist // len(top_genres)
            
            for genre, count in top_genres:
                genre_tracks = []
                for track in audio_items:
                    if track.get('Genres'):
                        track_genres = track['Genres'] if isinstance(track['Genres'], list) else [track['Genres']]
                        if genre in track_genres:
                            # Skip if already in user's collection
                            if track.get('Id') not in {t.get('Id') for t in reference_tracks}:
                                genre_tracks.append(track)
                
                # Add random selection from this genre
                if genre_tracks:
                    import random
                    selected = random.sample(genre_tracks, min(tracks_per_genre, len(genre_tracks)))
                    genre_mix_tracks.extend(selected)
            
            if genre_mix_tracks:
                if self.config.shuffle_tracks:
                    import random
                    random.shuffle(genre_mix_tracks)
                
                # Limit to max tracks
                limited_tracks = genre_mix_tracks[:self.config.max_tracks_per_playlist]
                
                playlist_name = f"Genre Mix - {user_name}"
                self.save_playlist("Personal", playlist_name, limited_tracks, user_id)
                self.logger.info(f"Created genre mix playlist for {user_name} with {len(limited_tracks)} tracks")
            else:
                self.logger.info(f"No genre mix tracks found for {user_name}")
                
        except Exception as e:
            self.logger.error(f"Error generating genre mix playlist for {user_name}: {e}")

    def generate_playlists(self):
        """Main playlist generation function"""
        self.logger.info("🎵 ========== STARTING JELLYJAMS PLAYLIST GENERATION ==========")
        self.logger.info(f"🔧 Configuration: Max tracks: {self.config.max_tracks_per_playlist}, Min tracks: {self.config.min_tracks_per_playlist}")
        self.logger.info(f"🔧 Playlist types: {', '.join(self.config.playlist_types)}")
        self.logger.info(f"🔧 Min albums per artist: {self.config.min_albums_per_artist}")
        self.logger.info(f"🔧 Excluded genres: {', '.join(self.config.excluded_genres) if self.config.excluded_genres else 'None'}")
        self.logger.info(f"🔧 Excluded artists: {', '.join(self.config.excluded_artists) if self.config.excluded_artists else 'None'}")
        
        # Test Jellyfin connection
        self.logger.info("🌐 Testing Jellyfin connection...")
        if not self.jellyfin.test_connection():
            self.logger.error("❌ Cannot connect to Jellyfin. Aborting playlist generation.")
            return
        self.logger.info("✅ Jellyfin connection successful")
        
        # Get audio items
        self.logger.info("🎶 Fetching audio items from Jellyfin...")
        audio_items = self.jellyfin.get_audio_items()
        if not audio_items:
            self.logger.warning("⚠️ No audio items found. Aborting playlist generation.")
            return
        
        self.logger.info(f"📊 Found {len(audio_items)} audio items in library")
        
        # Generate playlists based on configuration
        if 'Genre' in self.config.playlist_types:
            self.generate_genre_playlists(audio_items)
        
        if 'Year' in self.config.playlist_types:
            self.generate_year_playlists(audio_items)
        
        if 'Artist' in self.config.playlist_types:
            self.generate_artist_playlists(audio_items)
        
        if 'Personal' in self.config.playlist_types:
            self.generate_personalized_playlists(audio_items)
        
        # Trigger Jellyfin library scan to refresh playlists if enabled
        if self.config.trigger_library_scan:
            self.logger.info("Triggering Jellyfin media library scan to refresh playlists...")
            if self.jellyfin.trigger_library_scan():
                self.logger.info("✅ Media library scan triggered successfully")
            else:
                self.logger.warning("⚠️ Failed to trigger media library scan")
        
        self.logger.info("JellyJams playlist generation completed successfully!")

def main():
    """Main application entry point"""
    config = Config()
    logger = setup_logging(config)
    
    logger.info("🎵 JellyJams Generator Starting...")
    logger.info(f"Jellyfin URL: {config.jellyfin_url}")
    logger.info(f"Playlist Folder: {config.playlist_folder}")
    logger.info(f"Schedule Mode: {config.schedule_mode}")
    logger.info(f"Auto Generate on Startup: {config.auto_generate_on_startup}")
    logger.info(f"Playlist Types: {', '.join(config.playlist_types)}")
    
    # Validate configuration
    if not config.api_key:
        logger.error("JELLYFIN_API_KEY environment variable is required!")
        sys.exit(1)
    
    # Create playlist generator
    generator = PlaylistGenerator(config, logger)
    
    # Run initial generation only if enabled
    if config.auto_generate_on_startup:
        logger.info("🚀 Running initial playlist generation (startup generation enabled)")
        generator.generate_playlists()
    else:
        logger.info("⏸️ Skipping initial playlist generation (startup generation disabled)")
    
    # Setup scheduling based on configuration
    if config.schedule_mode == 'manual':
        logger.info("📋 Manual mode: Playlists will only be generated via web UI or API calls")
    elif config.schedule_mode == 'daily':
        # Parse schedule time (HH:MM format)
        try:
            hour, minute = map(int, config.schedule_time.split(':'))
            schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(generator.generate_playlists)
            logger.info(f"⏰ Daily generation scheduled at {config.schedule_time}")
        except ValueError:
            logger.error(f"Invalid schedule time format: {config.schedule_time}. Using default 00:00")
            schedule.every().day.at("00:00").do(generator.generate_playlists)
            logger.info("⏰ Daily generation scheduled at 00:00 (midnight)")
    elif config.schedule_mode == 'interval':
        schedule.every(config.generation_interval).hours.do(generator.generate_playlists)
        logger.info(f"⏰ Interval generation scheduled every {config.generation_interval} hours")
    else:
        logger.warning(f"Unknown schedule mode: {config.schedule_mode}. Defaulting to manual mode.")
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
