from datetime import datetime, timedelta
from app import db
from flask_login import UserMixin
import json



class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    oauth_provider = db.Column(db.String(20))
    oauth_id = db.Column(db.String(100))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    votes = db.relationship('Vote', backref='user', lazy=True)
    def __repr__(self):
        return f'<User {self.username}>'
    

class Creator(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    platform_ids = db.Column(db.Text)  
    videos = db.relationship('Video', backref='creator', lazy=True)
    def __repr__(self):
        return f'<Creator {self.name}>'
    def set_platform_ids(self, platform_dict):
        self.platform_ids = json.dumps(platform_dict)
    def get_platform_ids(self):
        if self.platform_ids:
            return json.loads(self.platform_ids)
        return {}
    

class BlacklistedCreator(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('creator.id'), nullable=False)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.relationship('Creator', backref='blacklist_entry')
    def __repr__(self):
        return f'<BlacklistedCreator {self.creator.name}>'
    

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    platform = db.Column(db.String(20), nullable=False)
    video_id = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    thumbnail_url = db.Column(db.String(500))
    duration_seconds = db.Column(db.Integer)
    upload_date = db.Column(db.DateTime)
    creator_id = db.Column(db.Integer, db.ForeignKey('creator.id'), nullable=False)
    similarity_hash = db.Column(db.String(256))  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    votes = db.relationship('Vote', backref='video', lazy=True)
    def __repr__(self):
        return f'<Video {self.title}>'
    

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    voting_period_id = db.Column(db.Integer, db.ForeignKey('voting_period.id'), nullable=False)
    rank = db.Column(db.Integer, nullable=False)  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def __repr__(self):
        return f'<Vote User:{self.user_id} Video:{self.video_id} Rank:{self.rank}>'
    

class VotingPeriod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    use_weighted_points = db.Column(db.Boolean, default=True)
    votes = db.relationship('Vote', backref='voting_period', lazy=True)
    def __repr__(self):
        return f'<VotingPeriod {self.name}>'
    @property
    def eligibility_start_date(self):
        first_day_previous_month = self.start_date.replace(day=1) - timedelta(days=1)
        return first_day_previous_month.replace(day=1)
    @property
    def eligibility_end_date(self):
        return self.start_date.replace(day=1) - timedelta(days=1)
    

class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    voting_period_id = db.Column(db.Integer, db.ForeignKey('voting_period.id'), nullable=True)
    is_public = db.Column(db.Boolean, default=True)
    is_historical = db.Column(db.Boolean, default=False)
    year = db.Column(db.Integer)  
    month = db.Column(db.Integer)  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    voting_period = db.relationship('VotingPeriod', backref='playlists')
    items = db.relationship('PlaylistItem', backref='playlist', lazy=True, 
                           order_by='PlaylistItem.position',
                           cascade='all, delete-orphan')
    def __repr__(self):
        return f'<Playlist {self.name}>'
    @property
    def is_standalone(self):
        return self.voting_period_id is None
    

class PlaylistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=True)
    custom_url = db.Column(db.String(500))
    custom_title = db.Column(db.String(200))
    custom_thumbnail_url = db.Column(db.String(500))
    custom_platform = db.Column(db.String(50))
    custom_creator = db.Column(db.String(100))
    custom_duration_seconds = db.Column(db.Integer)
    custom_upload_date = db.Column(db.DateTime)
    position = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    video = db.relationship('Video', backref='playlist_items')
    def __repr__(self):
        return f'<PlaylistItem {self.id} at position {self.position}>'
    
    
class HistoricalPlaylistSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    max_playlists = db.Column(db.Integer, default=10)
    spreadsheet_id = db.Column(db.String(200))
    worksheet_name = db.Column(db.String(100), default="Sheet1")
    last_import_date = db.Column(db.DateTime)
    auto_import_enabled = db.Column(db.Boolean, default=False)
    next_scheduled_import = db.Column(db.DateTime)
    import_limit_year = db.Column(db.Integer)  
    import_limit_month = db.Column(db.Integer)  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    def __repr__(self):
        return f'<HistoricalPlaylistSettings id={self.id}>'
