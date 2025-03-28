import os
import json
from dotenv import load_dotenv()

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SESSION_SECRET", "development-key-not-for-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///toptenpony.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    
    DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
    DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
    PUBLIC_URL = os.environ.get("PUBLIC_URL", None)
    
    SITE_NAME = "TopTenPonyVideos"
    PRIMARY_COLOR = "#9932CC"
    SECONDARY_COLOR = "#DEB0DF"
    BACKGROUND_COLOR = "#1D1D1D"
    TEXT_COLOR = "#F0F0F0"
    
    TEST_MODE = True
    TEST_USER = {
        "username": "TestUser",
        "email": "test@example.com",
        "is_admin": True
    }
    
    ADMIN_DISCORD_IDS = []
    
    SHOW_STANDALONE_PLAYLISTS = True
    ENABLE_HISTORICAL_PLAYLISTS = True
    HISTORICAL_PLAYLIST_SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1rEofPkliKppvttd8pEX8H6DtSljlfmQLdFR-SlyyX7E/edit?pli=1&gid=0#gid=0"
    
    @classmethod
    def load_from_file(cls, filepath="config.json"):
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    config_data = json.load(f)
                
                for key, value in config_data.items():
                    if hasattr(cls, key):
                        setattr(cls, key, value)
                return True
            except Exception as e:
                print(f"Error loading config file: {e}")
        return False
    
    @classmethod
    def save_to_file(cls, filepath="config.json"):
        config_data = {}
        for key in dir(cls):
            if not key.startswith("__") and not callable(getattr(cls, key)):
                value = getattr(cls, key)
                if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
                    config_data[key] = value
        
        try:
            with open(filepath, 'w') as f:
                json.dump(config_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config file: {e}")
            return False


Config.load_from_file()

if not os.path.exists("config.json"):
    Config.save_to_file()