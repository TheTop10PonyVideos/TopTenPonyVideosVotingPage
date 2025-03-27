import os
import logging
from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from sqlalchemy.orm import DeclarativeBase
from flask_wtf.csrf import CSRFProtect
from config import Config
logging.basicConfig(level=logging.DEBUG)
class Base(DeclarativeBase):
    pass
db = SQLAlchemy(model_class=Base)
csrf = CSRFProtect()
login_manager = LoginManager()
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = Config.SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = Config.SQLALCHEMY_ENGINE_OPTIONS
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = Config.SQLALCHEMY_TRACK_MODIFICATIONS
app.config["SITE_NAME"] = Config.SITE_NAME
app.config["PRIMARY_COLOR"] = Config.PRIMARY_COLOR
app.config["SECONDARY_COLOR"] = Config.SECONDARY_COLOR
app.config["BACKGROUND_COLOR"] = Config.BACKGROUND_COLOR
app.config["TEXT_COLOR"] = Config.TEXT_COLOR
app.config["TEST_MODE"] = Config.TEST_MODE
app.config["ADMIN_DISCORD_IDS"] = Config.ADMIN_DISCORD_IDS
app.config["SHOW_STANDALONE_PLAYLISTS"] = Config.SHOW_STANDALONE_PLAYLISTS
app.config["ENABLE_HISTORICAL_PLAYLISTS"] = Config.ENABLE_HISTORICAL_PLAYLISTS
app.config["HISTORICAL_PLAYLIST_SPREADSHEET_URL"] = Config.HISTORICAL_PLAYLIST_SPREADSHEET_URL
db.init_app(app)
csrf.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))
with app.app_context():
    from models import User, Vote, Video, Creator, BlacklistedCreator, VotingPeriod, Playlist, PlaylistItem, HistoricalPlaylistSettings
    db.create_all()
from routes import main_bp
from auth import auth_bp
from admin import admin_bp
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
import auth
