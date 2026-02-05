#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎵 TELEGRAM MUSIC BOT 2026 - Ultimate Version
Instagram, TikTok, Shazam, YouTube Music Search
Muallif: @Rustamov_v1
"""

import sys
import os
import asyncio
import tempfile
import subprocess
import hashlib
import re
import time
import signal
import json
import logging
import threading
from importlib.metadata import version
from pathlib import Path
from typing import Optional, Dict, List, Union, Any, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# ==================== KUTUBXONALAR ====================
try:
    import telebot
    from telebot import types
    from telebot.apihelper import ApiTelegramException
    from telebot.async_telebot import AsyncTeleBot
    TELEBOT_AVAILABLE = True
except ImportError:
    print("❌ telebot kutubxonasi topilmadi! O'rnatish: pip install pyTelegramBotAPI")
    sys.exit(1)

try:
    from shazamio import Shazam, Serialize
    SHAZAM_AVAILABLE = True
except ImportError:
    print("⚠️ shazamio kutubxonasi topilmadi. O'rnatish: pip install shazamio")
    SHAZAM_AVAILABLE = False

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    print("❌ yt-dlp kutubxonasi topilmadi! O'rnatish: pip install yt-dlp")
    sys.exit(1)

try:
    import aiohttp
    import aiofiles
    AIO_AVAILABLE = True
except ImportError:
    print("⚠️ aiohttp kutubxonasi topilmadi. O'rnatish: pip install aiohttp aiofiles")
    AIO_AVAILABLE = False

# ==================== SOZLAMALAR ====================
class Config:
    # Telegram Bot Token
    BOT_TOKEN = "8575775719:AAFk71ow9WR7crlONGpnP56qAZjO88Hj4eI"
    
    # Fayllar
    TEMP_DIR = Path("temp_files")
    TEMP_DIR.mkdir(exist_ok=True)
    COOKIES_FILE = TEMP_DIR / "youtube_cookies.txt"
    SESSIONS_FILE = TEMP_DIR / "sessions.json"
    
    # Cheklovlar
    MAX_FILE_SIZE = 49 * 1024 * 1024  # 49MB (Telegram limit: 50MB)
    MAX_DURATION = 3600  # 1 soat
    CLEANUP_INTERVAL = 300  # 5 daqiqa
    REQUEST_TIMEOUT = 45  # soniya
    DOWNLOAD_TIMEOUT = 600  # 10 daqiqa
    
    # Yuklash cheklovlari
    MAX_RETRIES = 3
    RATE_LIMIT_DELAY = 2  # soniya
    
    # Logging
    LOG_FILE = "music_bot.log"
    LOG_LEVEL = logging.INFO
    
    # Browser cookies paths
    BROWSER_PATHS = {
        'chrome': [
            '~/.config/google-chrome',
            '~/.config/chromium',
            '~/AppData/Local/Google/Chrome/User Data',
            '~/Library/Application Support/Google/Chrome'
        ],
        'firefox': [
            '~/.mozilla/firefox',
            '~/Library/Application Support/Firefox',
            '~/AppData/Roaming/Mozilla/Firefox'
        ],
        'brave': [
            '~/.config/BraveSoftware/Brave-Browser',
            '~/Library/Application Support/BraveSoftware/Brave-Browser'
        ]
    }
    
    # YouTube extractor args (PO Token muammolari uchun)
    YOUTUBE_EXTRACTOR_ARGS = {
        'youtube': {
            'player_client': ['android', 'ios', 'web', 'tv', 'mweb'],
            'player_skip': ['configs'],
            'throttled_rate': 'no',
        }
    }

# ==================== LOGGING ====================
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[94m',     # Ko'k
        'INFO': '\033[92m',      # Yashil
        'WARNING': '\033[93m',   # Sariq
        'ERROR': '\033[91m',     # Qizil
        'CRITICAL': '\033[91m',  # Qizil
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        message = super().format(record)
        return f"{log_color}{message}{self.COLORS['RESET']}"

# Loggerni sozlash
logger = logging.getLogger(__name__)
logger.setLevel(Config.LOG_LEVEL)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(Config.LOG_LEVEL)
console_formatter = ColoredFormatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File handler
file_handler = logging.FileHandler(Config.LOG_FILE, encoding='utf-8')
file_handler.setLevel(Config.LOG_LEVEL)
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ==================== GLOBAL STATE ====================
class GlobalState:
    """Global holatni boshqarish"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_state()
        return cls._instance
    
    def _init_state(self):
        self.user_sessions: Dict[int, Dict] = {}
        self.download_tasks: Dict[str, Dict] = {}
        self.rate_limits: Dict[int, datetime] = {}
        self.cookies_available = False
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.bot = None
        
        # Sessionlarni yuklash
        self.load_sessions()
        
        # Cookie faylini tekshirish
        self.check_cookies()
    
    def check_cookies(self):
        """Cookie faylini tekshirish"""
        if Config.COOKIES_FILE.exists():
            try:
                content = Config.COOKIES_FILE.read_text(encoding='utf-8')
                if content.strip() and 'youtube.com' in content:
                    self.cookies_available = True
                    logger.info("✅ YouTube cookie fayli topildi")
                else:
                    logger.warning("⚠️ Cookie fayli bo'sh yoki noto'g'ri formatda")
            except Exception as e:
                logger.error(f"❌ Cookie faylini o'qishda xatolik: {e}")
    
    def load_sessions(self):
        """Sessionlarni yuklash"""
        try:
            if Config.SESSIONS_FILE.exists():
                with open(Config.SESSIONS_FILE, 'r', encoding='utf-8') as f:
                    self.user_sessions = json.load(f)
                logger.info(f"✅ {len(self.user_sessions)} ta session yuklandi")
        except Exception as e:
            logger.error(f"❌ Sessionlarni yuklashda xatolik: {e}")
    
    def save_sessions(self):
        """Sessionlarni saqlash"""
        try:
            with open(Config.SESSIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.user_sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Sessionlarni saqlashda xatolik: {e}")
    
    def check_rate_limit(self, user_id: int) -> bool:
        """Rate limitni tekshirish"""
        now = datetime.now()
        if user_id in self.rate_limits:
            last_request = self.rate_limits[user_id]
            if (now - last_request).seconds < 2:  # 2 soniya
                return False
        self.rate_limits[user_id] = now
        return True

state = GlobalState()

# ==================== UTILITY FUNCTIONS ====================
def cleanup_old_files() -> None:
    """Eski fayllarni o'chirish"""
    try:
        current_time = time.time()
        deleted_count = 0
        
        for filepath in Config.TEMP_DIR.iterdir():
            if filepath.is_file() and filepath.suffix != '.json':
                file_age = current_time - filepath.stat().st_mtime
                if file_age > Config.CLEANUP_INTERVAL:
                    try:
                        filepath.unlink()
                        deleted_count += 1
                    except Exception as e:
                        logger.debug(f"Faylni o'chirishda xatolik: {e}")
        
        if deleted_count > 0:
            logger.info(f"🧹 {deleted_count} ta eski fayl o'chirildi")
            
    except Exception as e:
        logger.error(f"Cleanup xatosi: {e}")

def safe_delete(filepath: Optional[Union[str, Path]]) -> None:
    """Faylni xavfsiz o'chirish"""
    try:
        if filepath:
            path = Path(filepath)
            if path.exists() and path.is_file():
                path.unlink()
                logger.debug(f"🗑️ Fayl o'chirildi: {path.name}")
    except Exception as e:
        logger.debug(f"Delete xatosi: {e}")

def create_hash(text: str) -> str:
    """MD5 hash yaratish"""
    return hashlib.md5(str(text).encode('utf-8')).hexdigest()[:16]

def clean_filename(text: str) -> str:
    """Fayl nomini tozalash"""
    if not text:
        return "audio"
    
    # Maxsus belgilarni olib tashlash
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', text)
    text = re.sub(r'\s+', '_', text)
    text = re.sub(r'[^\w\-_\. ]', '', text)
    text = text[:100].strip('_')
    
    return text or "audio"

def format_duration(seconds: Optional[Union[int, float]]) -> str:
    """Vaqtni formatlash"""
    try:
        total_seconds = int(float(seconds))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        
        if hours > 0:
            return f" ({hours}:{minutes:02d}:{secs:02d})"
        else:
            return f" ({minutes}:{secs:02d})"
    except (TypeError, ValueError):
        return ""

def format_size(size_bytes: int) -> str:
    """Hajmni formatlash"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def is_instagram_url(url: str) -> bool:
    """Instagram URL tekshirish"""
    patterns = [
        r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|reels|tv)/([\w\-]+)/?',
        r'(?:https?://)?(?:www\.)?instagram\.com/(?:stories|s)/([\w\-]+)/?',
    ]
    url_lower = url.lower().strip()
    return any(re.search(pattern, url_lower) for pattern in patterns)

def is_tiktok_url(url: str) -> bool:
    """TikTok URL tekshirish"""
    patterns = [
        r'(?:https?://)?(?:www\.|vm\.|vt\.)?tiktok\.com/(?:@[\w\.]+/video/|\w+)',
        r'(?:https?://)?(?:www\.)?tiktok\.com/t/[\w\-]+/',
    ]
    url_lower = url.lower().strip()
    return any(re.search(pattern, url_lower) for pattern in patterns)

def is_youtube_url(url: str) -> bool:
    """YouTube URL tekshirish"""
    patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([\w\-]+)',
        r'(?:https?://)?(?:www\.)?youtu\.be/([\w\-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([\w\-]+)',
    ]
    url_lower = url.lower().strip()
    return any(re.search(pattern, url_lower) for pattern in patterns)

def validate_url(url: str) -> Tuple[bool, str]:
    """URLni tekshirish"""
    url = url.strip()
    
    if not url:
        return False, "❌ URL kiritilmadi"
    
    # URL formatini tekshirish
    url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    if not re.match(url_pattern, url, re.IGNORECASE):
        return False, "❌ Noto'g'ri URL formati"
    
    # Platformani aniqlash
    if is_instagram_url(url):
        return True, "instagram"
    elif is_tiktok_url(url):
        return True, "tiktok"
    elif is_youtube_url(url):
        return True, "youtube"
    else:
        return False, "❌ Qo'llab-quvvatlanmaydigan platforma"

# ==================== YOUTUBE COOKIES MANAGEMENT ====================
class CookieManager:
    """YouTube cookie manager"""
    
    @staticmethod
    def find_browser_cookies() -> Optional[Path]:
        """Browser cookie fayllarini qidirish"""
        browsers = ['chrome', 'firefox', 'brave', 'edge', 'opera']
        
        for browser in browsers:
            if browser in Config.BROWSER_PATHS:
                for path_pattern in Config.BROWSER_PATHS[browser]:
                    try:
                        path = Path(path_pattern).expanduser()
                        if path.exists():
                            # Cookie fayllarini qidirish
                            for cookie_file in path.rglob('Cookies'):
                                if cookie_file.is_file():
                                    logger.info(f"✅ {browser} cookie fayli topildi: {cookie_file}")
                                    return cookie_file
                    except Exception as e:
                        logger.debug(f"{browser} cookie qidiruvi: {e}")
        
        return None
    
    @staticmethod
    def extract_youtube_cookies() -> bool:
        """YouTube cookie'larini yt-dlp yordamida olish"""
        try:
            # Birinchi urinish: browser'dan cookie olish
            for browser in ['chrome', 'firefox', 'brave']:
                try:
                    cmd = [
                        'yt-dlp', '--cookies-from-browser', browser,
                        '--cookies', str(Config.COOKIES_FILE),
                        '--skip-download',
                        'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
                    ]
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False
                    )
                    
                    if result.returncode == 0 and Config.COOKIES_FILE.exists():
                        content = Config.COOKIES_FILE.read_text(encoding='utf-8')
                        if '.youtube.com' in content:
                            logger.info(f"✅ YouTube cookie'lar {browser} dan muvaffaqiyatli olindi")
                            state.cookies_available = True
                            return True
                except Exception as e:
                    logger.debug(f"{browser} cookie olish urinishi: {e}")
            
            # Ikkinchi urinish: manual cookie export guide
            logger.warning("""
            ⚠️ YouTube cookie'larini olish uchun quyidagi amallarni bajarishingiz kerak:
            
            1. Yangi inkognito oynada YouTube'ga kirishingiz
            2. Faqat shu oynada https://www.youtube.com/robots.txt sahifasiga o'tishingiz
            3. Browser extension (masalan, 'Get cookies.txt LOCALLY') yordamida cookie'larni eksport qilishingiz
            4. Eksport qilingan faylni 'temp_files/youtube_cookies.txt' papkasiga joylashtirishingiz
            
            Bu YouTube'dan 'bot emasman' degan xatoni oldini olish uchun zarur.
            """)
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Cookie olishda xatolik: {e}")
            return False

# ==================== YT-DLP CONFIGURATIONS ====================
class YDLConfig:
    """yt-dlp sozlamalari"""
    
    @staticmethod
    def get_base_options() -> Dict:
        """Asosiy sozlamalar"""
        options = {
            'quiet': True,
            'no_warnings': True,
            'no_color': True,
            'socket_timeout': Config.REQUEST_TIMEOUT,
            'retries': Config.MAX_RETRIES,
            'fragment_retries': Config.MAX_RETRIES,
            'skip_unavailable_fragments': True,
            'continue_dl': True,
            'noprogress': True,
            'concurrent_fragment_downloads': 4,
            'throttledratelimit': 1048576,
            'buffersize': 1048576,
            'http_chunk_size': 10485760,
        }
        
        # Agar cookie mavjud bo'lsa, qo'shamiz
        if state.cookies_available and Config.COOKIES_FILE.exists():
            options['cookiefile'] = str(Config.COOKIES_FILE)
        
        return options
    
    @staticmethod
    def get_youtube_options() -> Dict:
        """YouTube uchun maxsus sozlamalar"""
        options = YDLConfig.get_base_options()
        options.update({
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': str(Config.TEMP_DIR / 'youtube_%(id)s_%(title)s.%(ext)s'),
            'restrictfilenames': True,
            'windowsfilenames': True,
            'extractor_args': Config.YOUTUBE_EXTRACTOR_ARGS,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.youtube.com/',
                'Origin': 'https://www.youtube.com',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            },
            'compat_opts': ['no-youtube-unavailable-videos'],
            'extract_flat': False,
            'ignoreerrors': True,
            'nooverwrites': True,
        })
        return options
    
    @staticmethod
    def get_instagram_options() -> Dict:
        """Instagram uchun sozlamalar"""
        options = YDLConfig.get_base_options()
        options.update({
            'format': 'best[height<=720]/best',
            'outtmpl': str(Config.TEMP_DIR / 'instagram_%(id)s.%(ext)s'),
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            },
            'extractor_args': {
                'instagram': {
                    'app_id': '936619743392459',
                    'app_secret': 'f5d8c64e8b6e4c6b8b6e4c6b8b6e4c6b'
                }
            },
        })
        return options
    
    @staticmethod
    def get_tiktok_options() -> Dict:
        """TikTok uchun sozlamalar"""
        options = YDLConfig.get_base_options()
        options.update({
            'format': 'best[height<=720]/best',
            'outtmpl': str(Config.TEMP_DIR / 'tiktok_%(id)s.%(ext)s'),
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.tiktok.com/',
                'Origin': 'https://www.tiktok.com',
            },
        })
        return options
    
    @staticmethod
    def get_search_options() -> Dict:
        """Qidiruv uchun sozlamalar"""
        options = YDLConfig.get_base_options()
        options.update({
            'extract_flat': True,
            'force_generic_extractor': False,
            'default_search': 'ytsearch',
            'socket_timeout': 15,
            'retries': 2,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
        })
        return options

# ==================== DOWNLOAD MANAGER ====================
class DownloadManager:
    """Yuklash manageri"""
    
    @staticmethod
    def download_with_retry(url: str, options: Dict, platform: str) -> Optional[Path]:
        """Qayta urinishlar bilan yuklash"""
        for attempt in range(Config.MAX_RETRIES):
            try:
                logger.info(f"📥 Yuklash urinishi {attempt + 1}/{Config.MAX_RETRIES}: {url}")
                
                with yt_dlp.YoutubeDL(options) as ydl:
                    # Info olish
                    info = ydl.extract_info(url, download=False)
                    
                    # Agar video juda uzun bo'lsa
                    duration = info.get('duration', 0)
                    if duration > Config.MAX_DURATION:
                        logger.warning(f"⚠️ Video juda uzun: {duration} soniya")
                        return None
                    
                    # Yuklash
                    ydl.download([url])
                    
                    # Yuklangan faylni topish
                    video_id = info.get('id', 'unknown')
                    files = list(Config.TEMP_DIR.glob(f'*{video_id}*'))
                    
                    if files:
                        file_path = files[0]
                        file_size = file_path.stat().st_size
                        
                        if file_size > Config.MAX_FILE_SIZE:
                            logger.warning(f"⚠️ Fayl juda katta: {format_size(file_size)}")
                            safe_delete(file_path)
                            return None
                        
                        logger.info(f"✅ Muvaffaqiyatli yuklandi: {file_path.name} ({format_size(file_size)})")
                        return file_path
                
                # Agar fayl topilmasa, oxirgi o'zgartirilgan faylni topish
                files = sorted(
                    Config.TEMP_DIR.glob('*.*'),
                    key=lambda f: f.stat().st_mtime,
                    reverse=True
                )
                
                if files and (time.time() - files[0].stat().st_mtime) < 60:
                    return files[0]
                    
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                logger.error(f"❌ Yuklash xatosi (urinish {attempt + 1}): {error_msg}")
                
                # Agar cookie muammosi bo'lsa
                if 'Sign in to confirm' in error_msg or 'PO Token' in error_msg:
                    logger.warning("🔑 YouTube cookie muammosi. Cookie'ni yangilash kerak.")
                    CookieManager.extract_youtube_cookies()
                    # Cookie'ni yangilab qayta urinish
                    options['cookiefile'] = str(Config.COOKIES_FILE)
                    continue
                
                # Agar 429 xatosi bo'lsa (too many requests)
                if '429' in error_msg or 'Too Many Requests' in error_msg:
                    wait_time = (attempt + 1) * 5
                    logger.warning(f"⏳ Ko'p so'rovlar. {wait_time} soniya kutish...")
                    time.sleep(wait_time)
                    continue
                
                if attempt < Config.MAX_RETRIES - 1:
                    wait_time = (attempt + 1) * Config.RATE_LIMIT_DELAY
                    logger.info(f"⏳ {wait_time} soniya kutib, qayta urinish...")
                    time.sleep(wait_time)
            
            except Exception as e:
                logger.error(f"❌ Kutilmagan xatolik (urinish {attempt + 1}): {e}")
                if attempt < Config.MAX_RETRIES - 1:
                    time.sleep((attempt + 1) * 2)
        
        return None
    
    @staticmethod
    def download_youtube_audio(query: str, title: str = "") -> Optional[Path]:
        """YouTube'dan audio yuklash"""
        try:
            # Agar to'g'ridan-to'g'ri URL bo'lsa
            if is_youtube_url(query):
                url = query
            else:
                # Qidiruv uchun URL
                url = f"ytsearch1:{query}"
            
            options = YDLConfig.get_youtube_options()
            
            # Agar title berilgan bo'lsa, fayl nomini o'zgartiramiz
            if title:
                clean_title = clean_filename(title)
                options['outtmpl'] = str(Config.TEMP_DIR / f'audio_{clean_title}.%(ext)s')
            
            return DownloadManager.download_with_retry(url, options, 'youtube')
            
        except Exception as e:
            logger.error(f"❌ Audio yuklash xatosi: {e}")
            return None
    
    @staticmethod
    def download_instagram(url: str) -> Optional[Path]:
        """Instagram'dan yuklash"""
        try:
            options = YDLConfig.get_instagram_options()
            return DownloadManager.download_with_retry(url, options, 'instagram')
        except Exception as e:
            logger.error(f"❌ Instagram yuklash xatosi: {e}")
            return None
    
    @staticmethod
    def download_tiktok(url: str) -> Optional[Path]:
        """TikTok'dan yuklash"""
        try:
            options = YDLConfig.get_tiktok_options()
            return DownloadManager.download_with_retry(url, options, 'tiktok')
        except Exception as e:
            logger.error(f"❌ TikTok yuklash xatosi: {e}")
            return None

# ==================== SHAZAM RECOGNITION ====================
class MusicRecognizer:
    """Musiqa aniqlash"""
    
    @staticmethod
    async def recognize_audio_async(audio_bytes: bytes) -> Dict:
        """Shazam bilan musiqa aniqlash (async)"""
        if not SHAZAM_AVAILABLE:
            return {'found': False, 'error': 'Shazam kutubxonasi topilmadi'}
        
        temp_file = None
        try:
            # Vaqtinchalik fayl yaratish
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.mp3',
                dir=Config.TEMP_DIR
            ) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name
            
            # Shazam aniqlash
            shazam = Shazam()
            result = await shazam.recognize(temp_path)
            
            if result and 'track' in result:
                track = result['track']
                
                # Serialize qilish
                serialized = Serialize.full_track(result)
                
                return {
                    'found': True,
                    'title': track.get('title', 'Nomaʼlum'),
                    'artist': track.get('subtitle', 'Nomaʼlum'),
                    'album': track.get('sections', [{}])[0].get('metadata', [{}])[0].get('text', ''),
                    'year': track.get('year'),
                    'genre': track.get('genres', {}).get('primary', ''),
                    'label': track.get('label', ''),
                    'isrc': track.get('isrc', ''),
                    'serialized': serialized
                }
        
        except Exception as e:
            logger.error(f"❌ Shazam xatosi: {e}")
        
        finally:
            if temp_file:
                safe_delete(temp_path)
        
        return {'found': False}
    
    @staticmethod
    def recognize_audio_sync(audio_bytes: bytes) -> Dict:
        """Sync wrapper for Shazam"""
        try:
            if not SHAZAM_AVAILABLE:
                return {'found': False, 'error': 'Shazam kutubxonasi topilmadi'}
            
            # Yangi event loop yaratish
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Async funksiyani sync qilish
            future = asyncio.ensure_future(
                MusicRecognizer.recognize_audio_async(audio_bytes)
            )
            
            result = loop.run_until_complete(future)
            return result
            
        except Exception as e:
            logger.error(f"❌ Shazam sync xatosi: {e}")
            return {'found': False}

# ==================== AUDIO PROCESSING ====================
class AudioProcessor:
    """Audio processing"""
    
    @staticmethod
    def extract_audio_from_video(video_path: Union[str, Path], duration: int = 30) -> Optional[Path]:
        """Videodan audio ajratish"""
        try:
            video_path = Path(video_path)
            if not video_path.exists():
                return None
            
            audio_filename = f"{video_path.stem}_audio.mp3"
            audio_path = Config.TEMP_DIR / audio_filename
            
            # FFmpeg command
            command = [
                'ffmpeg',
                '-i', str(video_path),
                '-t', str(duration),  # Max duration
                '-vn',  # No video
                '-acodec', 'libmp3lame',
                '-ar', '44100',
                '-ac', '2',
                '-b:a', '192k',
                '-y',  # Overwrite
                str(audio_path)
            ]
            
            logger.info(f"🔧 Audio ajratilmoqda: {video_path.name}")
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"❌ FFmpeg xatosi: {result.stderr}")
                return None
            
            if audio_path.exists() and audio_path.stat().st_size > 1024:  # At least 1KB
                logger.info(f"✅ Audio ajratildi: {audio_path.name}")
                return audio_path
            else:
                logger.error("❌ Audio fayli yaratilmadi yoki bo'sh")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("❌ FFmpeg timeout (2 daqiqa)")
            return None
        except Exception as e:
            logger.error(f"❌ Audio extraction xatosi: {e}")
            return None
    
    @staticmethod
    def optimize_audio_for_telegram(audio_path: Path) -> Optional[Path]:
        """Telegram uchun audio optimizatsiyasi"""
        try:
            if not audio_path.exists():
                return None
            
            optimized_path = audio_path.parent / f"optimized_{audio_path.name}"
            
            command = [
                'ffmpeg',
                '-i', str(audio_path),
                '-acodec', 'libmp3lame',
                '-b:a', '128k',
                '-ar', '44100',
                '-ac', '2',
                '-id3v2_version', '3',
                '-write_id3v1', '1',
                '-y',
                str(optimized_path)
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60,
                check=False
            )
            
            if result.returncode == 0 and optimized_path.exists():
                # Asl faylni o'chirish
                safe_delete(audio_path)
                return optimized_path
            
            return audio_path  # Agar optimizatsiya ishlamasa, asl faylni qaytarish
            
        except Exception as e:
            logger.error(f"❌ Audio optimizatsiya xatosi: {e}")
            return audio_path

# ==================== TELEGRAM BOT ====================
class MusicBot:
    """Asosiy bot klassi"""
    
    def __init__(self):
        self.bot = telebot.TeleBot(Config.BOT_TOKEN, parse_mode='HTML')
        self.setup_handlers()
        self.running = False
    
    def setup_handlers(self):
        """Handlerlarni sozlash"""
        
        @self.bot.message_handler(commands=['start', 'help', 'boshlash'])
        def start_command(message):
            self.handle_start(message)
        
        @self.bot.message_handler(commands=['qidiruv', 'search', 'izla'])
        def search_command(message):
            self.handle_search_command(message)
        
        @self.bot.message_handler(commands=['stat', 'stats', 'holat'])
        def stats_command(message):
            self.handle_stats(message)
        
        @self.bot.message_handler(commands=['clean', 'tozalash'])
        def clean_command(message):
            self.handle_clean(message)
        
        @self.bot.message_handler(commands=['cookie', 'cookies'])
        def cookie_command(message):
            self.handle_cookie(message)
        
        @self.bot.message_handler(content_types=['audio', 'voice'])
        def audio_handler(message):
            self.handle_audio(message)
        
        @self.bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
        def text_handler(message):
            self.handle_text(message)
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def callback_handler(call):
            self.handle_callback(call)
    
    # ==================== COMMAND HANDLERS ====================
    
    def handle_start(self, message):
        """Start handler"""
        cleanup_old_files()
        
        welcome_text = """
🎵 <b>TELEGRAM MUSIC BOT 2026</b> 🎵

<b>🏆 Eng mukammal va tez bot!</b>

📱 <b>Quyidagilarni qila olaman:</b>
• Instagram video yuklash
• TikTok video yuklash  
• YouTube audio yuklash
• Musiqa aniqlash (Shazam)
• Qo'shiq qidirish va yuklash

<b>📋 Qanday ishlatish:</b>
1. Instagram/TikTok linkini yuboring
2. Audio/ovozli xabar yuboring (aniqlash uchun)
3. Qo'shiq nomini yozing (qidirish uchun)

<b>⚙️ Buyruqlar:</b>
/start - Botni ishga tushirish
/qidiruv - Qo'shiq qidirish
/stat - Bot statistikasi
/clean - Vaqtinchalik fayllarni tozalash
/cookie - Cookie sozlamalari

<b>👨‍💻 Dasturchi:</b> @Rustamov_v1
<b>📢 Kanal:</b> @Rustamov_Codes
"""
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🎵 Qidiruv", callback_data="nav_search"),
            types.InlineKeyboardButton("📊 Stat", callback_data="nav_stats"),
            types.InlineKeyboardButton("🧹 Tozalash", callback_data="nav_clean"),
            types.InlineKeyboardButton("🔧 Cookie", callback_data="nav_cookie")
        )
        
        try:
            self.bot.send_message(
                message.chat.id,
                welcome_text,
                reply_markup=markup,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"❌ Start xabarni yuborishda xatolik: {e}")
    
    def handle_search_command(self, message):
        """Qidiruv buyrug'i"""
        try:
            args = message.text.split(maxsplit=1)
            if len(args) > 1:
                query = args[1]
                self.process_search(message.chat.id, query, message.message_id)
            else:
                self.bot.send_message(
                    message.chat.id,
                    "🔍 <b>Qidiruv uchun qo'shiq nomini yozing:</b>\n\n"
                    "Masalan: <code>Doston Ergashev - Sevgi</code>",
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"❌ Search command xatosi: {e}")
    
    def handle_stats(self, message):
        """Statistika"""
        try:
            stats_text = f"""
📊 <b>BOT STATISTIKASI</b>

<b>👥 Foydalanuvchilar:</b> {len(state.user_sessions)}
<b>📁 Vaqtinchalik fayllar:</b> {len(list(Config.TEMP_DIR.glob('*.*')))}
<b>💾 Bo'sh joy:</b> {sum(f.stat().st_size for f in Config.TEMP_DIR.glob('*.*') if f.is_file()) // 1024 // 1024} MB
<b>🔧 Cookie holati:</b> {'✅ Mavjud' if state.cookies_available else '❌ Yo\'q'}

<b>⏰ Server vaqti:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
<b>🐍 Python versiyasi:</b> {sys.version.split()[0]}
"""
            
            self.bot.send_message(
                message.chat.id,
                stats_text,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"❌ Stats xatosi: {e}")
    
    def handle_clean(self, message):
        """Tozalash"""
        try:
            files_before = len(list(Config.TEMP_DIR.glob('*.*')))
            cleanup_old_files()
            files_after = len(list(Config.TEMP_DIR.glob('*.*')))
            
            cleaned = files_before - files_after
            
            self.bot.send_message(
                message.chat.id,
                f"🧹 <b>Tozalash bajarildi!</b>\n\n"
                f"<b>O'chirildi:</b> {cleaned} ta fayl\n"
                f"<b>Qoldi:</b> {files_after} ta fayl",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"❌ Clean xatosi: {e}")
    
    def handle_cookie(self, message):
        """Cookie sozlamalari"""
        try:
            if state.cookies_available:
                cookie_text = """
✅ <b>YouTube Cookie holati</b>

Cookie fayli mavjud va ishlayapti.
Bot YouTube'dan muammosiz yuklay oladi.
"""
            else:
                cookie_text = """
⚠️ <b>YouTube Cookie holati</b>

Cookie fayli topilmadi yoki ishlamayapti.
YouTube'dan yuklashda muammolar bo'lishi mumkin.

<b>Cookie'ni sozlash uchun:</b>
1. Yangi inkognito oyna oching
2. YouTube'ga kirib, robots.txt sahifasiga o'ting
3. Cookie'larni eksport qiling
4. 'temp_files/youtube_cookies.txt' fayliga saqlang
"""
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🔄 Cookie'ni yangilash", callback_data="update_cookies")
            )
            
            self.bot.send_message(
                message.chat.id,
                cookie_text,
                reply_markup=markup,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"❌ Cookie xatosi: {e}")
    
    # ==================== CONTENT HANDLERS ====================
    
    def handle_audio(self, message):
        """Audio/voice handler"""
        # Rate limit tekshirish
        if not state.check_rate_limit(message.chat.id):
            self.bot.reply_to(
                message,
                "⏳ <b>Iltimos, biroz kutib turing!</b>\n\n"
                "Bir vaqtning o'zida faqat bitta audio qayta ishlanadi.",
                parse_mode='HTML'
            )
            return
        
        # Status xabarini yuborish
        status_msg = self.bot.reply_to(
            message,
            "🎵 <b>Musiqa aniqlanmoqda...</b>",
            parse_mode='HTML'
        )
        
        # Yuklashni background thread'da bajarish
        threading.Thread(
            target=self._process_audio_background,
            args=(message, status_msg),
            daemon=True
        ).start()
    
    def _process_audio_background(self, message, status_msg):
        """Background audio processing"""
        audio_file_path = None
        
        try:
            # File ID olish
            if message.audio:
                file_id = message.audio.file_id
                file_name = message.audio.file_name or "audio"
            else:
                file_id = message.voice.file_id
                file_name = "voice_message.ogg"
            
            # File yuklab olish
            file_info = self.bot.get_file(file_id)
            audio_data = self.bot.download_file(file_info.file_path)
            
            # Shazam aniqlash
            self.bot.edit_message_text(
                "🎵 <b>Shazam bilan aniqlanmoqda...</b>",
                message.chat.id,
                status_msg.message_id,
                parse_mode='HTML'
            )
            
            result = MusicRecognizer.recognize_audio_sync(audio_data)
            
            if not result.get('found'):
                self.bot.edit_message_text(
                    "❌ <b>Musiqa aniqlanmadi</b>\n\n"
                    "Iltimos, boshqa audio yuboring yoki qo'shiq nomini yozing.",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
                return
            
            title = result['title']
            artist = result['artist']
            
            self.bot.edit_message_text(
                f"✅ <b>Topildi!</b>\n\n"
                f"🎵 <b>Nomi:</b> {title}\n"
                f"👤 <b>Ijrochi:</b> {artist}\n\n"
                f"⏳ <b>Yuklanmoqda...</b>",
                message.chat.id,
                status_msg.message_id,
                parse_mode='HTML'
            )
            
            # Audio yuklash
            query = f"{artist} {title}"
            audio_file_path = DownloadManager.download_youtube_audio(query, f"{artist} - {title}")
            
            if audio_file_path and audio_file_path.exists():
                # Optimizatsiya
                optimized_path = AudioProcessor.optimize_audio_for_telegram(audio_file_path)
                
                with open(optimized_path or audio_file_path, 'rb') as audio_file:
                    self.bot.send_audio(
                        message.chat.id,
                        audio_file,
                        title=title[:64],
                        performer=artist[:64],
                        caption=f"🎵 <b>{title}</b>\n👤 <b>{artist}</b>",
                        parse_mode='HTML'
                    )
                
                self.bot.delete_message(message.chat.id, status_msg.message_id)
                logger.info(f"✅ Audio yuborildi: {title} - {artist}")
                
            else:
                self.bot.edit_message_text(
                    f"✅ <b>Topildi!</b>\n\n"
                    f"🎵 <b>Nomi:</b> {title}\n"
                    f"👤 <b>Ijrochi:</b> {artist}\n\n"
                    f"❌ <b>Yuklanmadi</b>\n"
                    f"Qayta urinib ko'ring yoki to'g'ridan-to'g'ri YouTube linkini yuboring.",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
        
        except ApiTelegramException as e:
            logger.error(f"❌ Telegram API xatosi: {e}")
            try:
                self.bot.edit_message_text(
                    "❌ <b>Telegram API xatosi</b>\n\n"
                    "Iltimos, keyinroq qayta urinib ko'ring.",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
            except:
                pass
        
        except Exception as e:
            logger.error(f"❌ Audio processing xatosi: {e}")
            try:
                self.bot.edit_message_text(
                    "❌ <b>Xatolik yuz berdi</b>\n\n"
                    "Iltimos, keyinroq qayta urinib ko'ring.",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
            except:
                pass
        
        finally:
            safe_delete(audio_file_path)
    
    def handle_text(self, message):
        """Matn xabarlarini qayta ishlash"""
        text = message.text.strip()
        
        # Rate limit tekshirish
        if not state.check_rate_limit(message.chat.id):
            self.bot.reply_to(
                message,
                "⏳ <b>Iltimos, biroz kutib turing!</b>\n\n"
                "Bir vaqtning o'zida faqat bitta so'rov qayta ishlanadi.",
                parse_mode='HTML'
            )
            return
        
        # URL yoki qidiruvni aniqlash
        is_valid, result = validate_url(text)
        
        if is_valid:
            # URL bo'lsa
            platform = result
            threading.Thread(
                target=self._process_url_background,
                args=(message, text, platform),
                daemon=True
            ).start()
        else:
            # Qidiruv bo'lsa
            self.process_search(message.chat.id, text, message.message_id)
    
    def _process_url_background(self, message, url, platform):
        """Background URL processing"""
        status_msg = self.bot.reply_to(
            message,
            f"⏳ <b>Yuklanmoqda...</b>\n\n"
            f"📱 <b>Platforma:</b> {platform.capitalize()}",
            parse_mode='HTML'
        )
        
        video_path = None
        
        try:
            # Platformaga qarab yuklash
            if platform == 'instagram':
                video_path = DownloadManager.download_instagram(url)
            elif platform == 'tiktok':
                video_path = DownloadManager.download_tiktok(url)
            elif platform == 'youtube':
                video_path = DownloadManager.download_youtube_audio(url)
            
            if video_path and video_path.exists():
                # Fayl hajmini tekshirish
                file_size = video_path.stat().st_size
                
                if file_size > Config.MAX_FILE_SIZE:
                    self.bot.edit_message_text(
                        f"❌ <b>Fayl juda katta!</b>\n\n"
                        f"📊 <b>Hajmi:</b> {format_size(file_size)}\n"
                        f"📏 <b>Limit:</b> {format_size(Config.MAX_FILE_SIZE)}\n\n"
                        f"Kichikroq video yuboring.",
                        message.chat.id,
                        status_msg.message_id,
                        parse_mode='HTML'
                    )
                    safe_delete(video_path)
                    return
                
                # Video yuborish
                with open(video_path, 'rb') as video_file:
                    if platform == 'youtube':
                        # Audio yuborish
                        self.bot.send_audio(
                            message.chat.id,
                            video_file,
                            caption=f"🎵 <b>YouTube Audio</b>\n"
                                   f"🔗 <code>{url}</code>",
                            parse_mode='HTML'
                        )
                    else:
                        # Video yuborish
                        self.bot.send_video(
                            message.chat.id,
                            video_file,
                            caption=f"📱 <b>{platform.capitalize()}</b>\n"
                                   f"🔗 <code>{url}</code>",
                            supports_streaming=True,
                            parse_mode='HTML'
                        )
                
                self.bot.delete_message(message.chat.id, status_msg.message_id)
                logger.info(f"✅ {platform} yuborildi: {url}")
                
                # Kechiktirilgan o'chirish
                def delayed_delete():
                    time.sleep(30)
                    safe_delete(video_path)
                
                threading.Thread(target=delayed_delete, daemon=True).start()
                
            else:
                self.bot.edit_message_text(
                    f"❌ <b>Yuklanmadi!</b>\n\n"
                    f"📱 <b>Platforma:</b> {platform.capitalize()}\n"
                    f"🔗 <b>URL:</b> <code>{url}</code>\n\n"
                    f"Sabablar:\n"
                    f"• Video mavjud emas\n"
                    f"• Private video\n"
                    f"• Platforma bloklagan\n"
                    f"• Cookie muammosi (YouTube uchun)",
                    message.chat.id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
        
        except Exception as e:
            logger.error(f"❌ URL processing xatosi: {e}")
            self.bot.edit_message_text(
                "❌ <b>Xatolik yuz berdi</b>\n\n"
                "Iltimos, keyinroq qayta urinib ko'ring.",
                message.chat.id,
                status_msg.message_id,
                parse_mode='HTML'
            )
        
        finally:
            # Agar xatolik bo'lsa, darhol o'chirish
            if video_path and not video_path.exists():
                safe_delete(video_path)
    
    def process_search(self, chat_id: int, query: str, message_id: Optional[int] = None):
        """Qidiruvni qayta ishlash"""
        try:
            # Status xabari
            if message_id:
                try:
                    status_msg = self.bot.edit_message_text(
                        f"🔍 <b>Qidirilmoqda:</b> <code>{query[:50]}</code>",
                        chat_id,
                        message_id,
                        parse_mode='HTML'
                    )
                except:
                    status_msg = self.bot.send_message(
                        chat_id,
                        f"🔍 <b>Qidirilmoqda:</b> <code>{query[:50]}</code>",
                        parse_mode='HTML'
                    )
            else:
                status_msg = self.bot.send_message(
                    chat_id,
                    f"🔍 <b>Qidirilmoqda:</b> <code>{query[:50]}</code>",
                    parse_mode='HTML'
                )
            
            # Qidiruv
            with yt_dlp.YoutubeDL(YDLConfig.get_search_options()) as ydl:
                try:
                    info = ydl.extract_info(f"ytsearch50:{query}", download=False)
                    songs = info.get('entries', [])
                except Exception as e:
                    logger.error(f"❌ Qidiruv xatosi: {e}")
                    self.bot.edit_message_text(
                        "❌ <b>Qidiruvda xatolik</b>\n\n"
                        "Iltimos, keyinroq qayta urinib ko'ring.",
                        chat_id,
                        status_msg.message_id,
                        parse_mode='HTML'
                    )
                    return
            
            if not songs:
                self.bot.edit_message_text(
                    "❌ <b>Hech narsa topilmadi</b>\n\n"
                    "Boshqa nom bilan qidiring yoki to'g'ridan-to'g'ri YouTube linkini yuboring.",
                    chat_id,
                    status_msg.message_id,
                    parse_mode='HTML'
                )
                return
            
            # Session saqlash
            state.user_sessions[chat_id] = {
                'query': query,
                'songs': songs,
                'page': 0,
                'timestamp': datetime.now().isoformat()
            }
            state.save_sessions()
            
            # Natijalarni ko'rsatish
            self.show_search_results(chat_id, 0)
            self.bot.delete_message(chat_id, status_msg.message_id)
            
        except Exception as e:
            logger.error(f"❌ Process search xatosi: {e}")
            try:
                self.bot.send_message(
                    chat_id,
                    "❌ <b>Qidiruvda xatolik</b>\n\n"
                    "Iltimos, keyinroq qayta urinib ko'ring.",
                    parse_mode='HTML'
                )
            except:
                pass
    
    def show_search_results(self, chat_id: int, page: int = 0):
        """Qidiruv natijalarini ko'rsatish"""
        session = state.user_sessions.get(chat_id)
        if not session:
            self.bot.send_message(
                chat_id,
                "❌ <b>Sessiya muddati tugagan</b>\n\n"
                "Yangi qidiruv bering.",
                parse_mode='HTML'
            )
            return
        
        query = session['query']
        songs = session['songs']
        page_size = 10
        total_songs = len(songs)
        total_pages = (total_songs + page_size - 1) // page_size
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, total_songs)
        page_songs = songs[start_idx:end_idx]
        
        # Matnni yaratish
        text_lines = [
            f"🔍 <b>Qidiruv:</b> <code>{query}</code>",
            f"📄 <b>Sahifa:</b> {page + 1}/{total_pages} | <b>Jami:</b> {total_songs} ta",
            ""
        ]
        
        markup = types.InlineKeyboardMarkup(row_width=5)
        button_rows = []
        current_row = []
        
        for idx, song in enumerate(page_songs, 1):
            if not song:
                continue
            
            global_idx = start_idx + idx
            title = song.get('title', 'Nomaʼlum')[:40]
            duration = format_duration(song.get('duration'))
            
            text_lines.append(f"<b>{global_idx}.</b> {title}{duration}")
            
            url = song.get('url') or song.get('webpage_url')
            if url:
                h = create_hash(f"{url}_{global_idx}")
                hash_file = Config.TEMP_DIR / f"song_{h}.txt"
                hash_file.write_text(f"{url}|{title}|{global_idx}")
                
                btn = types.InlineKeyboardButton(str(global_idx), callback_data=f"dl_{h}")
                current_row.append(btn)
                
                if len(current_row) == 5:
                    button_rows.append(current_row)
                    current_row = []
        
        if current_row:
            button_rows.append(current_row)
        
        for row in button_rows:
            markup.add(*row)
        
        # Navigation
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton("⬅️ Oldingi", callback_data=f"page_{page-1}"))
        
        nav_buttons.append(types.InlineKeyboardButton("❌", callback_data="close_page"))
        
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton("Keyingi ➡️", callback_data=f"page_{page+1}"))
        
        if nav_buttons:
            markup.row(*nav_buttons)
        
        markup.row(
            types.InlineKeyboardButton("🔄 Yangi qidiruv", callback_data="nav_search"),
            types.InlineKeyboardButton("🏠 Bosh menyu", callback_data="nav_home")
        )
        
        session['page'] = page
        state.save_sessions()
        
        try:
            self.bot.send_message(
                chat_id,
                "\n".join(text_lines),
                reply_markup=markup,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"❌ Natijalarni ko'rsatishda xatolik: {e}")
    
    # ==================== CALLBACK HANDLERS ====================
    
    def handle_callback(self, call):
        """Callback query handler"""
        try:
            if call.data.startswith('dl_'):
                self.handle_download_callback(call)
            elif call.data.startswith('page_'):
                self.handle_page_callback(call)
            elif call.data.startswith('music_'):
                self.handle_music_callback(call)
            elif call.data.startswith('nav_'):
                self.handle_navigation_callback(call)
            elif call.data == 'close_page':
                self.handle_close_page(call)
            elif call.data == 'update_cookies':
                self.handle_update_cookies(call)
            
        except Exception as e:
            logger.error(f"❌ Callback handler xatosi: {e}")
            try:
                self.bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi", show_alert=True)
            except:
                pass
    
    def handle_download_callback(self, call):
        """Yuklash callback"""
        btn_hash = call.data.split('_')[1]
        self.bot.answer_callback_query(call.id, "⏳ Yuklanmoqda...")
        
        # Background thread
        threading.Thread(
            target=self._process_download_background,
            args=(call, btn_hash),
            daemon=True
        ).start()
    
    def _process_download_background(self, call, btn_hash):
        """Background download processing"""
        audio_file_path = None
        data_file = Config.TEMP_DIR / f"song_{btn_hash}.txt"
        
        try:
            if not data_file.exists():
                self.bot.answer_callback_query(call.id, "❌ Vaqt o'tgan", show_alert=True)
                return
            
            data = data_file.read_text().strip()
            parts = data.split('|', 2)
            
            if len(parts) == 3:
                url, title, song_num = parts
                title = f"{song_num}. {title}"
            elif len(parts) == 2:
                url, title = parts
            else:
                url = parts[0]
                title = 'Audio'
            
            # Yuklash
            audio_file_path = DownloadManager.download_youtube_audio(url, title)
            
            if audio_file_path and audio_file_path.exists():
                # Optimizatsiya
                optimized_path = AudioProcessor.optimize_audio_for_telegram(audio_file_path)
                
                with open(optimized_path or audio_file_path, 'rb') as audio_file:
                    self.bot.send_audio(
                        call.message.chat.id,
                        audio_file,
                        title=title[:64],
                        caption=f"✅ <b>{title}</b>",
                        parse_mode='HTML'
                    )
                
                logger.info(f"✅ Yuklandi: {title}")
                
            else:
                self.bot.send_message(
                    call.message.chat.id,
                    f"❌ <b>Yuklanmadi:</b> {title}\n\n"
                    "Iltimos, keyinroq qayta urinib ko'ring.",
                    parse_mode='HTML'
                )
            
            safe_delete(data_file)
            
        except Exception as e:
            logger.error(f"❌ Download callback xatosi: {e}")
            self.bot.send_message(
                call.message.chat.id,
                "❌ <b>Yuklashda xatolik</b>\n\n"
                "Iltimos, keyinroq qayta urinib ko'ring.",
                parse_mode='HTML'
            )
        
        finally:
            safe_delete(audio_file_path)
    
    def handle_page_callback(self, call):
        """Sahifa callback"""
        try:
            page = int(call.data.split('_')[1])
            self.bot.delete_message(call.message.chat.id, call.message.message_id)
            self.show_search_results(call.message.chat.id, page)
            self.bot.answer_callback_query(call.id)
        except Exception as e:
            logger.error(f"❌ Page callback xatosi: {e}")
    
    def handle_music_callback(self, call):
        """Musiqa aniqlash callback"""
        # Bu funksiya videodan musiqa aniqlash uchun
        btn_hash = call.data.split('_')[1]
        self.bot.answer_callback_query(call.id, "🎵 Musiqa aniqlanmoqda...")
        
        # Implementatsiyani keyinroq qo'shing
        self.bot.send_message(
            call.message.chat.id,
            "⚠️ <b>Bu funksiya hozircha ishlamayapti</b>\n\n"
            "Tez orada qo'shiladi.",
            parse_mode='HTML'
        )
    
    def handle_navigation_callback(self, call):
        """Navigation callback"""
        try:
            self.bot.delete_message(call.message.chat.id, call.message.message_id)
            
            if call.data == 'nav_home':
                self.handle_start(call.message)
            elif call.data == 'nav_search':
                self.bot.send_message(
                    call.message.chat.id,
                    "🔍 <b>Qidiruv uchun qo'shiq nomini yozing:</b>",
                    parse_mode='HTML'
                )
            elif call.data == 'nav_stats':
                self.handle_stats(call.message)
            elif call.data == 'nav_clean':
                self.handle_clean(call.message)
            elif call.data == 'nav_cookie':
                self.handle_cookie(call.message)
            
            self.bot.answer_callback_query(call.id)
            
        except Exception as e:
            logger.error(f"❌ Navigation callback xatosi: {e}")
    
    def handle_close_page(self, call):
        """Sahifani yopish"""
        try:
            self.bot.delete_message(call.message.chat.id, call.message.message_id)
            self.bot.answer_callback_query(call.id, "✅ Sahifa yopildi")
        except Exception as e:
            logger.error(f"❌ Close page xatosi: {e}")
    
    def handle_update_cookies(self, call):
        """Cookie'ni yangilash"""
        self.bot.answer_callback_query(call.id, "🔄 Cookie yangilanmoqda...")
        
        success = CookieManager.extract_youtube_cookies()
        
        if success:
            self.bot.send_message(
                call.message.chat.id,
                "✅ <b>Cookie muvaffaqiyatli yangilandi!</b>\n\n"
                "Endi YouTube'dan muammosiz yuklay olasiz.",
                parse_mode='HTML'
            )
        else:
            self.bot.send_message(
                call.message.chat.id,
                "❌ <b>Cookie yangilanmadi</b>\n\n"
                "Qo'lda sozlash talab qilinadi.\n\n"
                "1. Inkognito oyna oching\n"
                "2. YouTube'ga kiring\n"
                "3. robots.txt sahifasiga o'ting\n"
                "4. Cookie'larni eksport qiling\n"
                "5. temp_files/youtube_cookies.txt ga saqlang",
                parse_mode='HTML'
            )
    
    # ==================== BOT CONTROL ====================
    
    def start(self):
        """Botni ishga tushirish"""
        if self.running:
            logger.warning("⚠️ Bot allaqachon ishlamoqda")
            return
        
        self.running = True
        
        # Boshlang'ich tozalash
        cleanup_old_files()
        
        # Cookie'ni tekshirish
        if not state.cookies_available:
            logger.warning("⚠️ YouTube cookie fayli topilmadi")
            CookieManager.extract_youtube_cookies()
        
        # Davriy tozalashni ishga tushirish
        self._start_periodic_tasks()
        
        # Botni ishga tushirish
        logger.info("🚀 Bot ishga tushmoqda...")
        
        try:
            self.bot.infinity_polling(
                timeout=30,
                long_polling_timeout=30,
                logger_level=logging.WARNING,
                skip_pending=True
            )
        except KeyboardInterrupt:
            logger.info("\n🛑 Bot to'xtatilmoqda...")
            self.stop()
        except Exception as e:
            logger.error(f"❌ Bot ishga tushirishda xatolik: {e}")
            self.stop()
    
    def stop(self):
        """Botni to'xtatish"""
        self.running = False
        
        # Sessionlarni saqlash
        state.save_sessions()
        
        # Executor'ni to'xtatish
        state.executor.shutdown(wait=False)
        
        # Vaqtinchalik fayllarni tozalash
        cleanup_old_files()
        
        logger.info("✅ Bot to'xtatildi")
        sys.exit(0)
    
    def _start_periodic_tasks(self):
        """Davriy vazifalarni ishga tushirish"""
        
        def cleanup_task():
            while self.running:
                try:
                    time.sleep(Config.CLEANUP_INTERVAL)
                    cleanup_old_files()
                except Exception as e:
                    logger.error(f"❌ Cleanup task xatosi: {e}")
        
        def save_sessions_task():
            while self.running:
                try:
                    time.sleep(60)  # Har 1 daqiqa
                    state.save_sessions()
                except Exception as e:
                    logger.error(f"❌ Save sessions task xatosi: {e}")
        
        # Tasklarni ishga tushirish
        threading.Thread(target=cleanup_task, daemon=True).start()
        threading.Thread(target=save_sessions_task, daemon=True).start()
        
        logger.info("✅ Davriy tasklar ishga tushirildi")

# ==================== MAIN ====================
def main():
    """Asosiy funksiya"""
    
    # Banner
    print("\n" + "="*60)
    print("🎵 TELEGRAM MUSIC BOT 2026 - Ultimate Version")
    print("="*60)
    print(f"🐍 Python: {sys.version.split()[0]}")
    print(f"📦 yt-dlp: {version('yt-dlp') if YTDLP_AVAILABLE else 'N/A'}")
    print(f"🤖 Telebot: {version('pyTelegramBotAPI') if TELEBOT_AVAILABLE else 'N/A'}")
    print(f"🎶 Shazam: {version('shazamio') if SHAZAM_AVAILABLE else 'N/A'}")
    print("="*60)
    print("✅ Bot ishga tushmoqda...")
    print("⚡ Tez, barqaror va mukammal")
    print("📱 Instagram | TikTok | YouTube | Shazam")
    print("="*60 + "\n")
    
    # Signal handlers
    def signal_handler(signum, frame):
        logger.info(f"\n🛑 Signal {signum} qabul qilindi. Bot to'xtatilmoqda...")
        if 'bot' in globals():
            globals()['bot'].stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Botni yaratish va ishga tushirish
    try:
        bot = MusicBot()
        globals()['bot'] = bot
        bot.start()
    except Exception as e:
        logger.error(f"❌ Fatal xatolik: {e}")
        logger.info("🔄 5 soniyadan keyin qayta ishga tushiriladi...")
        time.sleep(5)
        
        # Qayta urinish
        try:
            bot = MusicBot()
            globals()['bot'] = bot
            bot.start()
        except Exception as e2:
            logger.error(f"❌ Qayta urinish muvaffaqiyatsiz: {e2}")
            sys.exit(1)

if __name__ == '__main__':
    main()
