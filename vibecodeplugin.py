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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

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
        
        # Media library scan after playlist creation
        self.trigger_library_scan = os.getenv('TRIGGER_LIBRARY_SCAN', 'true').lower() == 'true'
        
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
                if 'personal_playlist_new_users_default' in web_settings:
                    self.personal_playlist_new_users_default = bool(web_settings['personal_playlist_new_users_default'])
                if 'personal_playlist_min_user_tracks' in web_settings:
                    self.personal_playlist_min_user_tracks = int(web_settings['personal_playlist_min_user_tracks'])
                if 'discovery_max_songs_per_album' in web_settings:
                    self.discovery_max_songs_per_album = int(web_settings['discovery_max_songs_per_album'])
                if 'discovery_max_songs_per_artist' in web_settings:
                    self.discovery_max_songs_per_artist = int(web_settings['discovery_max_songs_per_artist'])
                if 'trigger_library_scan' in web_settings:
                    self.trigger_library_scan = bool(web_settings['trigger_library_scan'])
                    
                print(f"🎵  JellyJams web UI settings loaded - overriding environment variables")
                print(f"   Max tracks: {self.max_tracks_per_playlist}, Min tracks: {self.min_tracks_per_playlist}")
                print(f"   Playlist types: {', '.join(self.playlist_types)}")
                print(f"   Excluded genres: {', '.join(self.excluded_genres) if self.excluded_genres else 'None'}")
                
        except Exception as e:
            print(f"⚠️  Could not load web UI settings: {e}")
            print(f"   Using environment variables instead")

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
            'api_errors': 0,
            'last_test_time': None,
            'last_test_result': None,
            'response_times': []
        }
        self._initialize_client()
    
    def _initialize_client(self):
        if self.config.spotify_cover_art_enabled and self.config.spotify_client_id and self.config.spotify_client_secret:
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyClientCredentials
                
                client_credentials_manager = SpotifyClientCredentials(
                    client_id=self.config.spotify_client_id,
                    client_secret=self.config.spotify_client_secret
                )
                self.spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
                self.logger.info("Spotify API client initialized successfully")
            except ImportError:
                self.logger.warning("Spotipy library not found. Install with: pip install spotipy")
            except Exception as e:
                self.logger.error(f"Failed to initialize Spotify API client: {e}")
    
    def is_enabled(self) -> bool:
        """Check if Spotify integration is enabled and configured"""
        return self.spotify is not None
    
    def search_artist_playlist(self, artist_name: str) -> dict:
        """Search for 'This is {artist}' playlist on Spotify"""
        if not self.is_enabled():
            return None
            
        try:
            # Search for "This is {artist}" playlist
            query = f"This is {artist_name}"
            results = self.spotify.search(q=query, type='playlist', limit=10)
            
            # Look for exact or close matches
            for playlist in results['playlists']['items']:
                playlist_name = playlist['name'].lower()
                target_name = f"this is {artist_name.lower()}"
                
                # Check for exact match or close variations
                if (playlist_name == target_name or 
                    playlist_name == f"this is {artist_name.lower()}!" or
                    playlist_name.startswith(target_name)):
                    
                    self.logger.info(f"Found Spotify playlist: {playlist['name']} for artist: {artist_name}")
                    return playlist
            
            self.logger.debug(f"No 'This is {artist_name}' playlist found on Spotify")
            return None
            
        except Exception as e:
            self.logger.error(f"Error searching Spotify for artist {artist_name}: {e}")
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
        if not self.is_enabled():
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
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('/app/logs/vibecodeplugin.log')
        ]
    )
    return logging.getLogger('JellyJams')

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
            url = f"{self.config.jellyfin_url}/user_usage_stats/PlayActivity"
            params = {
                'user_id': user_id,
                'limit': limit,
                'media_type': 'Audio'
            }
            
            response = self.session.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                self.logger.info(f"Retrieved {len(data)} listening stats for user {user_id}")
                return data
            else:
                self.logger.warning(f"Playback reporting not available (status: {response.status_code})")
                return []
                
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Could not fetch listening stats: {e}")
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
    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.jellyfin = JellyfinAPI(config, logger)
        self.spotify = SpotifyClient(config, logger)

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
                return False
            
            # Copy and rename to folder.[original_extension] in the playlist directory
            # Preserve the original extension but rename to "folder"
            destination_filename = f"folder{found_extension}"
            destination_image = playlist_dir / destination_filename
            
            self.logger.info(f"Copying cover art: {source_image} -> {destination_image}")
            
            import shutil
            shutil.copy2(source_image, destination_image)
            
            self.logger.info(f"Successfully copied custom cover art: {source_image} -> {destination_image}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error copying custom cover art for {playlist_name}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

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

    def save_playlist(self, playlist_type: str, name: str, tracks: List[Dict], user_id: str = None):
        """Save playlist using Jellyfin's REST API with proper privacy controls and custom cover art"""
        self.logger.info(f"=== STARTING PLAYLIST CREATION ===")
        self.logger.info(f"Playlist Type: {playlist_type}")
        self.logger.info(f"Playlist Name: {name}")
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
            
            self.logger.info(f"Creating {privacy_text} {playlist_type} playlist: {name} with {len(track_ids)} tracks")
            
            # Check if playlist already exists and delete it
            self.logger.info(f"Checking for existing playlist: {name}")
            existing_playlist = self.jellyfin.get_playlist_by_name(name, user_id)
            if existing_playlist:
                self.logger.info(f"Playlist '{name}' already exists, deleting old version with ID: {existing_playlist.get('Id')}")
                delete_success = self.jellyfin.delete_playlist(existing_playlist['Id'])
                if delete_success:
                    self.logger.info(f"Successfully deleted existing playlist")
                else:
                    self.logger.warning(f"Failed to delete existing playlist")
            else:
                self.logger.info(f"No existing playlist found with name: {name}")
            
            # Create the playlist via API with proper privacy settings
            self.logger.info(f"Creating new playlist via Jellyfin API...")
            result = self.jellyfin.create_playlist(name, track_ids, user_id, is_public)
            
            if result['success']:
                self.logger.info(f"✅ Successfully created {privacy_text} playlist '{name}' with {result['track_count']} tracks")
                
                # Create directory for cover art storage
                playlist_dir = Path(self.config.playlist_folder) / name
                playlist_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created playlist directory: {playlist_dir}")
                
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
                
                # For artist playlists, try Spotify cover art if no custom cover was added
                if not cover_added and "This is" in name and self.spotify.is_enabled():
                    self.logger.info(f"Attempting to apply Spotify cover art for artist playlist...")
                    # Extract artist name from "This is [Artist]!" format
                    artist_name = name.replace("This is ", "").replace("!", "").strip()
                    self.logger.info(f"Extracted artist name: {artist_name}")
                    if self.spotify.get_artist_cover_art(artist_name, playlist_dir):
                        cover_added = True
                        self.logger.info(f"✅ Applied Spotify cover art for artist playlist: {name}")
                    else:
                        self.logger.info(f"No Spotify cover art found for artist: {artist_name}")
                
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
        """Generate playlists by genre"""
        self.logger.info("Generating genre-based playlists...")
        
        # Group tracks by genre
        genre_tracks = {}
        for item in audio_items:
            if not item.get('Genres'):
                continue
            
            # Parse genres - handle both list and semicolon-separated string formats
            genres = []
            if isinstance(item['Genres'], list):
                for genre_item in item['Genres']:
                    if isinstance(genre_item, str) and ';' in genre_item:
                        # Split semicolon-separated genres
                        genres.extend([g.strip() for g in genre_item.split(';') if g.strip()])
                    else:
                        genres.append(genre_item)
            elif isinstance(item['Genres'], str):
                # Handle string format with semicolons
                if ';' in item['Genres']:
                    genres = [g.strip() for g in item['Genres'].split(';') if g.strip()]
                else:
                    genres = [item['Genres']]
            
            # Process each individual genre
            for genre in genres:
                if genre in self.config.excluded_genres:
                    continue
                    
                if genre not in genre_tracks:
                    genre_tracks[genre] = []
                genre_tracks[genre].append(item)
        
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
        """Generate playlists by year"""
        self.logger.info("Generating year-based playlists...")
        
        # Group tracks by year
        year_tracks = {}
        for item in audio_items:
            year = item.get('ProductionYear')
            if not year:
                continue
                
            if year not in year_tracks:
                year_tracks[year] = []
            year_tracks[year].append(item)
        
        # Create playlists for each year
        for year, tracks in year_tracks.items():
            if len(tracks) < self.config.min_tracks_per_playlist:
                continue
            
            # Check artist diversity - count unique artists in this year
            unique_artists = set()
            for track in tracks:
                if track.get('Artists'):
                    for artist in track['Artists']:
                        unique_artists.add(artist)
            
            if len(unique_artists) < self.config.min_artist_diversity:
                self.logger.info(f"Skipping year '{year}' - only {len(unique_artists)} artists (minimum: {self.config.min_artist_diversity})")
                continue
                
            # Limit tracks and shuffle if requested
            limited_tracks = tracks[:self.config.max_tracks_per_playlist]
            if self.config.shuffle_tracks:
                import random
                random.shuffle(limited_tracks)
            
            playlist_name = f"Back to {year}"
            self.save_playlist("Year", playlist_name, limited_tracks)
            self.logger.info(f"Created year playlist '{playlist_name}' with {len(limited_tracks)} tracks from {len(unique_artists)} artists")

    def generate_artist_playlists(self, audio_items: List[Dict]):
        """Generate playlists by artist"""
        self.logger.info("Generating artist-based playlists...")
        
        # Group tracks by artist
        artist_tracks = {}
        for item in audio_items:
            if not item.get('Artists'):
                continue
                
            for artist in item['Artists']:
                if artist not in artist_tracks:
                    artist_tracks[artist] = []
                artist_tracks[artist].append(item)
        
        # Create playlists for each artist
        for artist, tracks in artist_tracks.items():
            if len(tracks) < self.config.min_tracks_per_playlist:
                continue
                
            # Limit tracks and shuffle if requested
            limited_tracks = tracks[:self.config.max_tracks_per_playlist]
            if self.config.shuffle_tracks:
                import random
                random.shuffle(limited_tracks)
            
            playlist_name = f"This is {artist}!"
            playlist_dir = self.save_playlist("Artist", playlist_name, limited_tracks)
            
            # Download Spotify cover art if enabled
            if playlist_dir and self.spotify.is_enabled():
                self.spotify.get_artist_cover_art(artist, playlist_dir)

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
            # Try to get listening stats first
            listening_stats = self.jellyfin.get_user_listening_stats(user_id, limit=50)
            
            if listening_stats:
                # Extract track IDs from listening stats and find corresponding tracks
                top_tracks = []
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
                
            else:
                # Fallback to favorite tracks if no listening stats available
                self.logger.info(f"No listening stats available for {user_name}, using favorites")
                top_tracks = self.jellyfin.get_user_favorite_items(user_id)
            
            if top_tracks:
                # Limit to configured max tracks
                limited_tracks = top_tracks[:self.config.max_tracks_per_playlist]
                if self.config.shuffle_tracks:
                    import random
                    random.shuffle(limited_tracks)
                
                playlist_name = f"Top Tracks - {user_name}"
                self.save_playlist("Personal", playlist_name, limited_tracks, user_id)
                self.logger.info(f"Created top tracks playlist for {user_name} with {len(limited_tracks)} tracks")
            else:
                self.logger.info(f"No top tracks found for {user_name}")
                
        except Exception as e:
            self.logger.error(f"Error generating top tracks playlist for {user_name}: {e}")

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
        self.logger.info("Starting JellyJams playlist generation...")
        
        # Test Jellyfin connection
        if not self.jellyfin.test_connection():
            self.logger.error("Cannot connect to Jellyfin. Aborting playlist generation.")
            return
        
        # Get audio items
        audio_items = self.jellyfin.get_audio_items()
        if not audio_items:
            self.logger.warning("No audio items found. Aborting playlist generation.")
            return
        
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
    logger.info(f"Generation Interval: {config.generation_interval} hours")
    logger.info(f"Playlist Types: {', '.join(config.playlist_types)}")
    
    # Validate configuration
    if not config.api_key:
        logger.error("JELLYFIN_API_KEY environment variable is required!")
        sys.exit(1)
    
    # Create playlist generator
    generator = PlaylistGenerator(config, logger)
    
    # Run initial generation
    generator.generate_playlists()
    
    # Schedule regular generation
    schedule.every(config.generation_interval).hours.do(generator.generate_playlists)
    
    logger.info(f"Scheduled to run every {config.generation_interval} hours")
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
