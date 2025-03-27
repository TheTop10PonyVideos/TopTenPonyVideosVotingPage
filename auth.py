import os
import requests
from functools import wraps
from flask import Blueprint, redirect, url_for, flash, request, render_template, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from models import User
auth_bp = Blueprint('auth', __name__)
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
DISCORD_API_ENDPOINT = "https://discord.com/api"
def get_discord_oauth_url():
    from config import Config
    public_url = Config.PUBLIC_URL
    if public_url:
        base_url = public_url.rstrip('/')
    else:
        base_url = request.host_url.rstrip('/') if request else None
    redirect_uri = f"{base_url}/discord/callback" if base_url else None
    if DISCORD_CLIENT_ID and redirect_uri:
        oauth_url = f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri={redirect_uri}&response_type=code&scope=identify%20email"
        print(f"Discord OAuth URL: {oauth_url}")  
        return oauth_url
    return None
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import current_app
        from config import Config
        if not current_user.is_authenticated:
            flash("You must be logged in to access this page.", "danger")
            return redirect(url_for('auth.login'))
        is_admin = current_user.is_admin
        if not is_admin and current_user.oauth_provider == "discord":
            admin_discord_ids = current_app.config.get('ADMIN_DISCORD_IDS', [])
            if current_user.oauth_id in admin_discord_ids:
                current_user.is_admin = True
                db.session.commit()
                is_admin = True
        if not is_admin:
            flash("You don't have permission to access this page.", "danger")
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function
@auth_bp.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    from config import Config
    from flask import current_app
    if current_app.config.get('TEST_MODE', False):
        from models import User
        test_user = User.query.filter_by(email=Config.TEST_USER['email']).first()
        if not test_user:
            test_user = User(
                username=Config.TEST_USER['username'],
                email=Config.TEST_USER['email'],
                is_admin=Config.TEST_USER['is_admin'],
                oauth_provider="test",
                oauth_id="test"
            )
            db.session.add(test_user)
            db.session.commit()
        login_user(test_user)
        flash('Logged in as test user.', 'success')
        return redirect(url_for('main.index'))
    return render_template('login.html')
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.index'))
@auth_bp.route('/discord/login')
def discord_login():
    oauth_url = get_discord_oauth_url()
    if not oauth_url:
        flash("Discord OAuth is not configured.", "danger")
        return redirect(url_for('auth.login'))
    return redirect(oauth_url)
@auth_bp.route('/discord/callback')
def discord_callback():
    if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET:
        flash("Discord OAuth is not configured.", "danger")
        return redirect(url_for('auth.login'))
    code = request.args.get('code')
    if not code:
        flash("Authorization failed.", "danger")
        return redirect(url_for('auth.login'))
    from config import Config
    public_url = Config.PUBLIC_URL
    if public_url:
        base_url = public_url.rstrip('/')
    else:
        base_url = request.host_url.rstrip('/')
    redirect_uri = f"{base_url}/discord/callback"
    print(f"Discord callback redirect URI: {redirect_uri}")  
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'scope': 'identify email'
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        token_response = requests.post(f'{DISCORD_API_ENDPOINT}/oauth2/token', data=data, headers=headers)
        print(f"Discord token response status: {token_response.status_code}")
        if token_response.status_code != 200:
            error_data = token_response.json() if token_response.text else {"error": "Unknown error"}
            print(f"Discord token error: {error_data}")
            error_description = error_data.get('error_description', 'No details provided')
            flash(f"Failed to authenticate with Discord: {error_description}", "danger")
            return redirect(url_for('auth.login'))
    except Exception as e:
        print(f"Exception getting Discord token: {str(e)}")
        flash(f"Error connecting to Discord: {str(e)}", "danger")
        return redirect(url_for('auth.login'))
    token_data = token_response.json()
    access_token = token_data.get('access_token')
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        user_response = requests.get(f'{DISCORD_API_ENDPOINT}/users/@me', headers=headers)
        print(f"Discord user info response status: {user_response.status_code}")
        if user_response.status_code != 200:
            error_data = user_response.json() if user_response.text else {"error": "Unknown error"}
            print(f"Discord user info error: {error_data}")
            error_message = error_data.get('message', 'No details provided')
            flash(f"Failed to get user info from Discord: {error_message}", "danger")
            return redirect(url_for('auth.login'))
    except Exception as e:
        print(f"Exception getting Discord user info: {str(e)}")
        flash(f"Error connecting to Discord: {str(e)}", "danger")
        return redirect(url_for('auth.login'))
    user_data = user_response.json()
    discord_id = user_data.get('id')
    username = user_data.get('username')
    email = user_data.get('email')
    if not email:
        flash("Email not provided by Discord.", "danger")
        return redirect(url_for('auth.login'))
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            username=username,
            email=email,
            oauth_provider="discord",
            oauth_id=discord_id
        )
        db.session.add(user)
        db.session.commit()
    login_user(user)
    flash(f"Welcome, {user.username}!", "success")
    return redirect(url_for('main.index'))
