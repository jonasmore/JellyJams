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
        self.playlist_types = os.getenv('PLAYLIST_TYPES', 'Genre,Year,Artist').split(',')
        
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
                    
                print(f"🎵  JellyJams web UI settings loaded - overriding environment variables")
                print(f"   Max tracks: {self.max_tracks_per_playlist}, Min tracks: {self.min_tracks_per_playlist}")
                print(f"   Playlist types: {', '.join(self.playlist_types)}")
                print(f"   Excluded genres: {', '.join(self.excluded_genres) if self.excluded_genres else 'None'}")
                
        except Exception as e:
            print(f"⚠️  Could not load web UI settings: {e}")
            print(f"   Using environment variables instead")

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

class PlaylistGenerator:
    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.jellyfin = JellyfinAPI(config, logger)

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

    def save_playlist(self, playlist_type: str, name: str, tracks: List[Dict]):
        """Save playlist to XML file"""
        try:
            # Create playlist name with JellyJams prefix
            playlist_name = f"JellyJams {playlist_type}: {name}"
            
            # Create playlist directory
            playlist_dir = Path(self.config.playlist_folder) / playlist_name
            playlist_dir.mkdir(parents=True, exist_ok=True)
            
            # Create XML content
            xml_content = self.create_playlist_xml(playlist_name, tracks)
            
            # Save to file
            playlist_file = playlist_dir / 'playlist.xml'
            with open(playlist_file, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            self.logger.info(f"Created playlist: {playlist_name} with {len(tracks)} tracks")
            
        except Exception as e:
            self.logger.error(f"Error saving playlist {playlist_name}: {e}")

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
                
            # Limit tracks and shuffle if requested
            limited_tracks = tracks[:self.config.max_tracks_per_playlist]
            if self.config.shuffle_tracks:
                import random
                random.shuffle(limited_tracks)
            
            self.save_playlist("Genre", genre, limited_tracks)

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
                
            # Limit tracks and shuffle if requested
            limited_tracks = tracks[:self.config.max_tracks_per_playlist]
            if self.config.shuffle_tracks:
                import random
                random.shuffle(limited_tracks)
            
            self.save_playlist("Year", str(year), limited_tracks)

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
            
            self.save_playlist("Artist", artist, limited_tracks)

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
