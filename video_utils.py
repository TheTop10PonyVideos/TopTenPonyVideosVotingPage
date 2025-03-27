import os
import re
import json
import requests
import logging
from datetime import datetime, timedelta
import hashlib
from urllib.parse import urlparse, parse_qs
from difflib import SequenceMatcher
import yt_dlp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
ydl_opts = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': 'in_playlist',
    'skip_download': True,
    'format': 'best',
    'no_color': True,
    'ignoreerrors': True,
    'noplaylist': False,  # We'll handle playlists ourselves
    'geo_bypass': True,
    'nocheckcertificate': True,
    'socket_timeout': 10,  # Timeout after 10 seconds
}
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
VIMEO_ACCESS_TOKEN = os.environ.get("VIMEO_ACCESS_TOKEN")
DAILYMOTION_API_KEY = os.environ.get("DAILYMOTION_API_KEY")
if YOUTUBE_API_KEY:
    youtube_client = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
else:
    youtube_client = None
SUPPORTED_PLATFORMS = [
    "youtube", "ponytube", "bilibili", "vimeo", "dailymotion", 
    "thishorsie", "tiktok", "twitter", "odysee", "newgrounds", "bluesky"
]
class VideoExtractor:
    @staticmethod
    def extract_video_info(url):
        
        parsed_url = urlparse(url)
        hostname = parsed_url.netloc.lower()
        
        if 'youtube.com' in hostname or 'youtu.be' in hostname:
            return VideoExtractor._extract_youtube(url, parsed_url)
        elif 'pony.tube' in hostname:
            return VideoExtractor._extract_ponytube(url, parsed_url)
        elif 'bilibili.com' in hostname:
            return VideoExtractor._extract_bilibili(url, parsed_url)
        elif 'vimeo.com' in hostname:
            return VideoExtractor._extract_vimeo(url, parsed_url)
        elif 'dailymotion.com' in hostname:
            return VideoExtractor._extract_dailymotion(url, parsed_url)
        elif 'thishorsie.rocks' in hostname:
            return VideoExtractor._extract_thishorsie(url, parsed_url)
        elif 'tiktok.com' in hostname:
            return VideoExtractor._extract_tiktok(url, parsed_url)
        elif 'twitter.com' in hostname or 'x.com' in hostname:
            return VideoExtractor._extract_twitter(url, parsed_url)
        elif 'odysee.com' in hostname:
            return VideoExtractor._extract_odysee(url, parsed_url)
        elif 'newgrounds.com' in hostname:
            return VideoExtractor._extract_newgrounds(url, parsed_url)
        elif 'bsky.app' in hostname:
            return VideoExtractor._extract_bluesky(url, parsed_url)
        else:
            raise ValueError(f"Unsupported platform: {hostname}")
    
    @staticmethod
    def _extract_youtube(url, parsed_url):
        if 'youtu.be' in parsed_url.netloc:
            video_id = parsed_url.path.strip('/')
        else:
            query_params = parse_qs(parsed_url.query)
            video_id = query_params.get('v', [None])[0]
        
        if not video_id:
            raise ValueError("Could not extract YouTube video ID")
        
        if YOUTUBE_API_KEY and youtube_client is not None:
            try:
                request = youtube_client.videos().list(
                    part="snippet,contentDetails,statistics",
                    id=video_id
                )
                response = request.execute()
                
                if not response.get('items'):
                    raise ValueError("YouTube video not found or is private")
                
                video_data = response['items'][0]
                snippet = video_data['snippet']
                
                duration_str = video_data['contentDetails']['duration']
                duration_seconds = VideoExtractor._parse_iso_duration(duration_str)
                
                upload_date = datetime.strptime(snippet['publishedAt'], "%Y-%m-%dT%H:%M:%SZ")
                
                embeddable = video_data['contentDetails'].get('embeddable', True)
                
                return {
                    'title': snippet['title'],
                    'platform': 'youtube',
                    'video_id': video_id,
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'thumbnail_url': snippet.get('thumbnails', {}).get('high', {}).get('url'),
                    'duration_seconds': duration_seconds,
                    'upload_date': upload_date,
                    'creator_name': snippet['channelTitle'],
                    'creator_id': snippet['channelId'],
                    'description': snippet.get('description', ''),
                    'view_count': int(video_data['statistics'].get('viewCount', 0)),
                    'embeddable': embeddable
                }
            except HttpError as e:
                logger.warning(f"YouTube API error: {str(e)}. Falling back to yt-dlp.")
            except Exception as e:
                logger.warning(f"Error extracting YouTube video info with API: {str(e)}. Falling back to yt-dlp.")
        else:
            logger.info("YouTube API key not configured. Falling back to yt-dlp.")
            
        try:
            info = VideoExtractor._extract_with_yt_dlp(url)
            
            info['platform'] = 'youtube'
            info['video_id'] = video_id
            
            return info
        except Exception as e:
            logger.error(f"yt-dlp extraction failed for YouTube: {str(e)}")
            raise ValueError(f"Failed to extract YouTube video info: {str(e)}")
    
    @staticmethod
    def _extract_ponytube(url, parsed_url):
        path_parts = parsed_url.path.strip('/').split('/')
        if len(path_parts) < 2 or path_parts[0] != 'w':
            raise ValueError("Invalid Pony.tube URL format")
        
        video_id = path_parts[1]
        
        try:
            info = VideoExtractor._extract_with_yt_dlp(url)
            
            info['platform'] = 'ponytube'
            info['video_id'] = video_id
            
            return info
        except Exception as e:
            logger.warning(f"yt-dlp extraction failed for PonyTube: {str(e)}")
            
            response = requests.get(url)
            
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
            creator_match = re.search(r'<meta name="author" content="([^"]+)"', response.text)
            thumbnail_match = re.search(r'<meta property="og:image" content="([^"]+)"', response.text)
            
            if not title_match:
                raise ValueError("Could not extract video title from Pony.tube")
            
            title = title_match.group(1)
            creator_name = creator_match.group(1) if creator_match else "Unknown Creator"
            thumbnail_url = thumbnail_match.group(1) if thumbnail_match else None
            
            date_match = re.search(r'<time datetime="([^"]+)"', response.text)
            upload_date = None
            if date_match:
                try:
                    upload_date = datetime.strptime(date_match.group(1)[:10], '%Y-%m-%d')
                except Exception:
                    pass
            
            duration_match = re.search(r'<meta itemprop="duration" content="([^"]+)"', response.text)
            duration_seconds = 0
            if duration_match:
                try:
                    duration_str = duration_match.group(1)
                    duration_seconds = VideoExtractor._parse_iso_duration(duration_str)
                except Exception:
                    pass
            
            return {
                'title': title,
                'platform': 'ponytube',
                'video_id': video_id,
                'url': url,
                'thumbnail_url': thumbnail_url,
                'duration_seconds': duration_seconds,
                'upload_date': upload_date,
                'creator_name': creator_name,
                'creator_id': creator_name,  # Using name as ID
                'description': '',
            }
    
    @staticmethod
    def _extract_bilibili(url, parsed_url):
        if 'video' in parsed_url.path:
            video_id = parsed_url.path.split('/')[-1]
        else:
            raise ValueError("Unsupported Bilibili URL format")
        
        try:
            info = VideoExtractor._extract_with_yt_dlp(url)
            
            info['platform'] = 'bilibili'
            info['video_id'] = video_id
                
            return info
        except Exception as e:
            logger.warning(f"yt-dlp extraction failed for Bilibili: {str(e)}")
            
            response = requests.get(url)
            
            title_match = re.search(r'<title>(.*?) - bilibili', response.text)
            creator_match = re.search(r'<meta name="author" content="([^"]+)"', response.text)
            thumbnail_match = re.search(r'<meta property="og:image" content="([^"]+)"', response.text)
            
            if not title_match:
                raise ValueError("Could not extract video title from Bilibili")
            
            title = title_match.group(1)
            creator_name = creator_match.group(1) if creator_match else "Unknown Creator"
            thumbnail_url = thumbnail_match.group(1) if thumbnail_match else None
            
            duration_match = re.search(r'"duration":\s*(\d+)', response.text)
            duration_seconds = int(duration_match.group(1)) if duration_match else 0
            
            date_match = re.search(r'"pubdate":\s*(\d+)', response.text)
            upload_date = None
            if date_match:
                try:
                    upload_timestamp = int(date_match.group(1))
                    upload_date = datetime.fromtimestamp(upload_timestamp)
                except Exception:
                    upload_date = datetime.now() - timedelta(days=7)
            
            return {
                'title': title,
                'platform': 'bilibili',
                'video_id': video_id,
                'url': url,
                'thumbnail_url': thumbnail_url,
                'duration_seconds': duration_seconds,
                'upload_date': upload_date,
                'creator_name': creator_name,
                'creator_id': creator_name,
                'description': '',
            }
    
    @staticmethod
    def _extract_vimeo(url, parsed_url):
        path_parts = parsed_url.path.strip('/').split('/')
        if not path_parts or not path_parts[0].isdigit():
            raise ValueError("Invalid Vimeo URL format")
        
        video_id = path_parts[0]
        
        try:
            info = VideoExtractor._extract_with_yt_dlp(url)
            
            info['platform'] = 'vimeo'
            info['video_id'] = video_id
            
            return info
        except Exception as e:
            logger.warning(f"yt-dlp extraction failed for Vimeo: {str(e)}")
            
            if not VIMEO_ACCESS_TOKEN:
                response = requests.get(url)
                
                title_match = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
                creator_match = re.search(r'"owner":\s*{\s*"name":\s*"([^"]+)"', response.text)
                thumbnail_match = re.search(r'<meta property="og:image" content="([^"]+)"', response.text)
                
                title = title_match.group(1) if title_match else "Untitled"
                creator_name = creator_match.group(1) if creator_match else "Unknown Creator"
                thumbnail_url = thumbnail_match.group(1) if thumbnail_match else None
                
                duration_match = re.search(r'"duration":\s*(\d+)', response.text)
                duration_seconds = int(duration_match.group(1)) if duration_match else 0
                
                date_match = re.search(r'"uploadDate":\s*"([^"]+)"', response.text)
                upload_date = None
                if date_match:
                    try:
                        upload_date = datetime.strptime(date_match.group(1)[:10], '%Y-%m-%d')
                    except Exception:
                        upload_date = datetime.now() - timedelta(days=7)  # Fallback
                
                return {
                    'title': title,
                    'platform': 'vimeo',
                    'video_id': video_id,
                    'url': url,
                    'thumbnail_url': thumbnail_url,
                    'duration_seconds': duration_seconds,
                    'upload_date': upload_date,
                    'creator_name': creator_name,
                    'creator_id': creator_name,
                    'description': '',
                }
            
            api_url = f"https://api.vimeo.com/videos/{video_id}"
            headers = {'Authorization': f'Bearer {VIMEO_ACCESS_TOKEN}'}
            response = requests.get(api_url, headers=headers)
            data = response.json()
            
            if response.status_code != 200:
                raise ValueError(f"Vimeo API error: {data.get('error')}")
            
            duration_seconds = data.get('duration', 0)
            
            upload_date_str = data.get('created_time')
            upload_date = datetime.strptime(upload_date_str, "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None) if upload_date_str else None
            
            return {
                'title': data.get('name', 'Untitled'),
                'platform': 'vimeo',
                'video_id': video_id,
                'url': data.get('link', url),
                'thumbnail_url': data.get('pictures', {}).get('sizes', [{}])[-1].get('link'),
                'duration_seconds': duration_seconds,
                'upload_date': upload_date,
                'creator_name': data.get('user', {}).get('name', 'Unknown'),
                'creator_id': str(data.get('user', {}).get('id', '')),
                'description': data.get('description', ''),
            }
    
    @staticmethod
    def _extract_dailymotion(url, parsed_url):
        path_parts = parsed_url.path.strip('/').split('/')
        if len(path_parts) < 2 or path_parts[0] != 'video':
            raise ValueError("Invalid Dailymotion URL format")
        
        video_id = path_parts[1].split('_')[0]
        
        try:
            info = VideoExtractor._extract_with_yt_dlp(url)
            
            info['platform'] = 'dailymotion'
            info['video_id'] = video_id
            
            return info
        except Exception as e:
            logger.warning(f"yt-dlp extraction failed for Dailymotion: {str(e)}")
            
            try:
                api_url = f"https://api.dailymotion.com/video/{video_id}?fields=title,duration,created_time,owner.username,thumbnail_url"
                response = requests.get(api_url)
                data = response.json()
                
                if response.status_code != 200 or data.get('error'):
                    raise ValueError(f"Dailymotion API error: {data.get('error', {}).get('message')}")
                
                upload_timestamp = data.get('created_time', 0)
                upload_date = datetime.fromtimestamp(upload_timestamp) if upload_timestamp else None
                
                return {
                    'title': data.get('title', 'Untitled'),
                    'platform': 'dailymotion',
                    'video_id': video_id,
                    'url': f"https://www.dailymotion.com/video/{video_id}",
                    'thumbnail_url': data.get('thumbnail_url'),
                    'duration_seconds': data.get('duration', 0),
                    'upload_date': upload_date,
                    'creator_name': data.get('owner.username', 'Unknown'),
                    'creator_id': data.get('owner.username', ''),
                    'description': '',  # Not provided in this API response
                }
            except Exception as e:
                logger.warning(f"Dailymotion API extraction failed: {str(e)}")
                
                response = requests.get(url)
                
                title_match = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
                creator_match = re.search(r'<meta name="author" content="([^"]+)"', response.text)
                thumbnail_match = re.search(r'<meta property="og:image" content="([^"]+)"', response.text)
                
                title = title_match.group(1) if title_match else "Untitled"
                creator_name = creator_match.group(1) if creator_match else "Unknown Creator"
                thumbnail_url = thumbnail_match.group(1) if thumbnail_match else None
                
                duration_match = re.search(r'duration["\']:\s*["\']?(\d+)["\']?', response.text, re.IGNORECASE)
                duration_seconds = int(duration_match.group(1)) if duration_match else 0
                
                date_match = re.search(r'uploadDate["\']:\s*["\']([^"\']+)["\']', response.text, re.IGNORECASE)
                upload_date = None
                if date_match:
                    try:
                        upload_date = datetime.strptime(date_match.group(1)[:10], '%Y-%m-%d')
                    except Exception:
                        upload_date = datetime.now() - timedelta(days=7)  # Fallback
                
                return {
                    'title': title,
                    'platform': 'dailymotion',
                    'video_id': video_id,
                    'url': url,
                    'thumbnail_url': thumbnail_url,
                    'duration_seconds': duration_seconds,
                    'upload_date': upload_date,
                    'creator_name': creator_name,
                    'creator_id': creator_name,
                    'description': '',
                }
    
    @staticmethod
    def _extract_thishorsie(url, parsed_url):
        video_id = parsed_url.path.strip('/').split('/')[-1]
        
        try:
            info = VideoExtractor._extract_with_yt_dlp(url)
            
            info['platform'] = 'thishorsie'
            info['video_id'] = video_id
            
            return info
        except Exception as e:
            logger.warning(f"yt-dlp extraction failed for ThisHorsie: {str(e)}")
            
            response = requests.get(url)
            
            title_match = re.search(r'<title>(.*?)</title>', response.text)
            creator_match = re.search(r'<meta name="author" content="([^"]+)"', response.text)
            thumbnail_match = re.search(r'<meta property="og:image" content="([^"]+)"', response.text)
            
            title = title_match.group(1) if title_match else "Untitled"
            creator_name = creator_match.group(1) if creator_match else "Unknown Creator"
            thumbnail_url = thumbnail_match.group(1) if thumbnail_match else None
            
            duration_match = re.search(r'duration["\']:\s*["\']([^"\']+)["\']', response.text, re.IGNORECASE)
            duration_seconds = 0
            if duration_match:
                try:
                    duration_str = duration_match.group(1)
                    if ':' in duration_str:
                        parts = duration_str.split(':')
                        if len(parts) == 2:  # MM:SS
                            duration_seconds = int(parts[0]) * 60 + int(parts[1])
                        elif len(parts) == 3:  # HH:MM:SS
                            duration_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    else:
                        duration_seconds = int(float(duration_str))
                except Exception:
                    pass
            
            date_match = re.search(r'uploadDate["\']:\s*["\']([^"\']+)["\']', response.text, re.IGNORECASE)
            upload_date = None
            if date_match:
                try:
                    upload_date = datetime.strptime(date_match.group(1)[:10], '%Y-%m-%d')
                except Exception:
                    upload_date = datetime.now() - timedelta(days=7)
            
            return {
                'title': title,
                'platform': 'thishorsie',
                'video_id': video_id,
                'url': url,
                'thumbnail_url': thumbnail_url,
                'duration_seconds': duration_seconds,
                'upload_date': upload_date,
                'creator_name': creator_name,
                'creator_id': creator_name,
                'description': '',
            }
    
    @staticmethod
    def _extract_tiktok(url, parsed_url):
        video_id = None
        creator_handle = None
        
        path_parts = parsed_url.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[0] == 'video':
            video_id = path_parts[1]
        else:
            match = re.search(r'tiktok\.com/(@[^/]+)/video/(\d+)', url)
            if match:
                video_id = match.group(2)
                creator_handle = match.group(1)
            else:
                raise ValueError("Could not extract TikTok video ID")
        
        try:
            info = VideoExtractor._extract_with_yt_dlp(url)
            
            info['platform'] = 'tiktok'
            info['video_id'] = video_id
            
            if creator_handle and not info.get('creator_name'):
                info['creator_name'] = creator_handle
                info['creator_id'] = creator_handle
                
            return info
        except Exception as e:
            logger.warning(f"yt-dlp extraction failed for TikTok: {str(e)}")
            
            return {
                'title': "TikTok Video",
                'platform': 'tiktok',
                'video_id': video_id,
                'url': url,
                'thumbnail_url': None,
                'duration_seconds': 15,  # Default assumption for TikTok
                'upload_date': datetime.now() - timedelta(days=1),  # Assume recent
                'creator_name': creator_handle if creator_handle else "Unknown",
                'creator_id': creator_handle if creator_handle else "",
                'description': '',
            }
    
    @staticmethod
    def _extract_twitter(url, parsed_url):
        match = re.search(r'twitter\.com/[^/]+/status/(\d+)', url) or re.search(r'x\.com/[^/]+/status/(\d+)', url)
        if not match:
            raise ValueError("Could not extract Twitter/X tweet ID")
        
        tweet_id = match.group(1)
        
        username_match = re.search(r'(twitter|x)\.com/([^/]+)', url)
        username = username_match.group(2) if username_match else "Unknown"
        
        try:
            info = VideoExtractor._extract_with_yt_dlp(url)
            
            info['platform'] = 'twitter'
            info['video_id'] = tweet_id
            
            if username and not info.get('creator_name'):
                info['creator_name'] = username
                info['creator_id'] = username
                
            if not info.get('title'):
                info['title'] = f"Tweet by {username}"
                
            return info
        except Exception as e:
            logger.warning(f"yt-dlp extraction failed for Twitter/X: {str(e)}")
            
            return {
                'title': f"Tweet by {username}",
                'platform': 'twitter',
                'video_id': tweet_id,
                'url': url,
                'thumbnail_url': None,
                'duration_seconds': 30,  # Default assumption for Twitter/X videos
                'upload_date': datetime.now() - timedelta(days=1),  # Assume recent
                'creator_name': username,
                'creator_id': username,
                'description': '',
            }
    
    @staticmethod
    def _extract_odysee(url, parsed_url):
        path_parts = parsed_url.path.strip('/').split('/')
        if len(path_parts) < 2:
            raise ValueError("Invalid Odysee URL format")
        
        channel = path_parts[0].lstrip('@')
        video_slug = path_parts[1]
        
        try:
            info = VideoExtractor._extract_with_yt_dlp(url)
            
            info['platform'] = 'odysee'
            info['video_id'] = video_slug
            
            if channel and not info.get('creator_name'):
                info['creator_name'] = channel
                info['creator_id'] = channel
                
            return info
        except Exception as e:
            logger.warning(f"yt-dlp extraction failed for Odysee: {str(e)}")
            
            response = requests.get(url)
            
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
            thumbnail_match = re.search(r'<meta property="og:image" content="([^"]+)"', response.text)
            
            title = title_match.group(1) if title_match else "Untitled"
            thumbnail_url = thumbnail_match.group(1) if thumbnail_match else None
            
            duration_match = re.search(r'"duration":\s*(\d+)', response.text)
            duration_seconds = int(duration_match.group(1)) if duration_match else 0
            
            upload_date = datetime.now() - timedelta(days=7)  # Assume recent
            
            return {
                'title': title,
                'platform': 'odysee',
                'video_id': video_slug,
                'url': url,
                'thumbnail_url': thumbnail_url,
                'duration_seconds': duration_seconds,
                'upload_date': upload_date,
                'creator_name': channel,
                'creator_id': channel,
                'description': '',
            }
    
    @staticmethod
    def _extract_newgrounds(url, parsed_url):
        
        match = re.search(r'newgrounds\.com/portal/view/(\d+)', url)
        if not match:
            raise ValueError("Invalid Newgrounds URL format")
        
        video_id = match.group(1)
        
        try:
            info = VideoExtractor._extract_with_yt_dlp(url)
            
            info['platform'] = 'newgrounds'
            info['video_id'] = video_id
            
            return info
        except Exception as e:
            logger.warning(f"yt-dlp extraction failed for Newgrounds: {str(e)}")
            
            response = requests.get(url)
            
            title_match = re.search(r'<title>(.*?) by (.*?) \|', response.text)
            thumbnail_match = re.search(r'<meta property="og:image" content="([^"]+)"', response.text)
            
            if title_match:
                title = title_match.group(1)
                creator_name = title_match.group(2)
            else:
                title = "Untitled"
                creator_name = "Unknown Creator"
            
            thumbnail_url = thumbnail_match.group(1) if thumbnail_match else None
            
            duration_match = re.search(r'itemprop="duration"[^>]*>(\d+):(\d+)<', response.text)
            duration_seconds = 0
            if duration_match:
                try:
                    minutes = int(duration_match.group(1))
                    seconds = int(duration_match.group(2))
                    duration_seconds = minutes * 60 + seconds
                except Exception:
                    pass
            
            date_match = re.search(r'itemprop="datePublished"[^>]*>([^<]+)<', response.text)
            upload_date = None
            if date_match:
                try:
                    date_str = date_match.group(1).strip()
                    for fmt in ['%b %d, %Y', '%B %d, %Y', '%Y-%m-%d']:
                        try:
                            upload_date = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                except Exception:
                    upload_date = datetime.now() - timedelta(days=7)  # Fallback
            
            return {
                'title': title,
                'platform': 'newgrounds',
                'video_id': video_id,
                'url': url,
                'thumbnail_url': thumbnail_url,
                'duration_seconds': duration_seconds,
                'upload_date': upload_date,
                'creator_name': creator_name,
                'creator_id': creator_name,
                'description': '',
            }
    
    @staticmethod
    def _extract_bluesky(url, parsed_url):
        
        match = re.search(r'bsky\.app/profile/([^/]+)/post/([^/]+)', url)
        if not match:
            raise ValueError("Invalid Bluesky URL format")
        
        username = match.group(1)
        post_id = match.group(2)
        
        try:
            info = VideoExtractor._extract_with_yt_dlp(url)
            
            info['platform'] = 'bluesky'
            info['video_id'] = post_id
            
            if username and not info.get('creator_name'):
                info['creator_name'] = username
                info['creator_id'] = username
            
            return info
        except Exception as e:
            logger.warning(f"yt-dlp extraction failed for Bluesky: {str(e)}")
            
            response = requests.get(url)
            
            title = f"Bluesky post by {username}"
            
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
            if title_match:
                title = title_match.group(1)
                
            thumbnail_match = re.search(r'<meta property="og:image" content="([^"]+)"', response.text)
            thumbnail_url = thumbnail_match.group(1) if thumbnail_match else None
            
            video_match = re.search(r'<video[^>]*src="([^"]+)"', response.text)
            if video_match:
                logger.info(f"Found video element in Bluesky post: {video_match.group(1)}")
            
            upload_date = datetime.now() - timedelta(days=1)
            
            duration_seconds = 30  # Default to 30 seconds
            
            description_match = re.search(r'<meta property="og:description" content="([^"]+)"', response.text)
            description = description_match.group(1) if description_match else ""
            
            return {
                'title': title,
                'platform': 'bluesky',
                'video_id': post_id,
                'url': url,
                'thumbnail_url': thumbnail_url,
                'duration_seconds': duration_seconds,
                'upload_date': upload_date,
                'creator_name': username,
                'creator_id': username,
                'description': description,
            }
    
    @staticmethod
    def _parse_iso_duration(duration_str):
        
        hours = re.search(r'(\d+)H', duration_str)
        minutes = re.search(r'(\d+)M', duration_str)
        seconds = re.search(r'(\d+)S', duration_str)
        
        total_seconds = 0
        if hours:
            total_seconds += int(hours.group(1)) * 3600
        if minutes:
            total_seconds += int(minutes.group(1)) * 60
        if seconds:
            total_seconds += int(seconds.group(1))
        
        return total_seconds
    
    @staticmethod
    def _extract_with_yt_dlp(url):
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info.get('_type') == 'playlist':
                    if not info.get('entries'):
                        raise ValueError("No videos found in playlist")
                    info = info['entries'][0]
                
                upload_date = None
                if info.get('upload_date'):
                    try:
                        upload_date = datetime.strptime(info['upload_date'], '%Y%m%d')
                    except Exception as e:
                        logger.warning(f"Could not parse upload date: {e}")
                
                platform = None
                if info.get('extractor_key'):
                    platform_map = {
                        'Youtube': 'youtube',
                        'Dailymotion': 'dailymotion',
                        'Vimeo': 'vimeo',
                        'TikTok': 'tiktok',
                        'Twitter': 'twitter',
                        'Bilibili': 'bilibili',
                        'Odysee': 'odysee'
                    }
                    platform = platform_map.get(info.get('extractor_key'), info.get('extractor_key').lower())
                
                creator_name = info.get('uploader', 'Unknown Creator')
                creator_id = info.get('uploader_id', creator_name)
                
                return {
                    'title': info.get('title', 'Untitled'),
                    'platform': platform or 'unknown',
                    'video_id': info.get('id', ''),
                    'url': info.get('webpage_url', url),
                    'thumbnail_url': info.get('thumbnail'),
                    'duration_seconds': info.get('duration', 0),
                    'upload_date': upload_date,
                    'creator_name': creator_name,
                    'creator_id': creator_id,
                    'description': info.get('description', ''),
                    'view_count': info.get('view_count', 0)
                }
        except Exception as e:
            logger.error(f"Error extracting video info with yt-dlp: {str(e)}")
            raise ValueError(f"Error extracting video info: {str(e)}")
    
    @staticmethod
    def generate_similarity_hash(video_info):
        
        key_data = f"{video_info['title'].lower()}|{video_info['creator_name'].lower()}"
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()
    
    @staticmethod
    def check_similarity(video1, video2, threshold=0.8):
        
        title_similarity = SequenceMatcher(None, video1['title'].lower(), video2['title'].lower()).ratio()
        
        creator_similarity = SequenceMatcher(None, video1['creator_name'].lower(), video2['creator_name'].lower()).ratio()
        
        overall_similarity = (title_similarity * 0.7) + (creator_similarity * 0.3)
        
        return overall_similarity >= threshold
def validate_video(url, voting_period):
    
    try:
        video_info = VideoExtractor.extract_video_info(url)
        
        platform = video_info.get('platform')
        if platform not in SUPPORTED_PLATFORMS:
            return False, f"Platform '{platform}' is not supported"
        
        duration = video_info.get('duration_seconds', 0)
        if duration < 30:
            return False, f"Video is too short ({duration}s). Minimum 30 seconds required."
        
        upload_date = video_info.get('upload_date')
        if not upload_date:
            return False, "Could not determine video upload date"
        
        eligibility_start = voting_period.eligibility_start_date
        eligibility_end = voting_period.eligibility_end_date
        
        if not (eligibility_start <= upload_date <= eligibility_end):
            return False, f"Video was not uploaded in the eligible period ({eligibility_start.strftime('%Y-%m-%d')} to {eligibility_end.strftime('%Y-%m-%d')})"
        
        return True, video_info
    
    except Exception as e:
        logger.error(f"Error validating video: {str(e)}")
        return False, str(e)
