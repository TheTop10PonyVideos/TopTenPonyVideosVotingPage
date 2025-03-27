from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, Response, send_file, jsonify
from flask_login import login_required, current_user
from auth import admin_required
from app import db
from models import User, Vote, Video, Creator, BlacklistedCreator, VotingPeriod, Playlist, PlaylistItem, HistoricalPlaylistSettings
from datetime import datetime, timedelta
from config import Config
from io import StringIO, BytesIO
import csv
import json
import os
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urlparse, parse_qs
from sqlalchemy import func, desc, case, and_
admin_bp = Blueprint('admin', __name__)
@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    user_count = User.query.count()
    video_count = Video.query.count()
    vote_count = Vote.query.count()
    blacklist_count = BlacklistedCreator.query.count()
    voting_periods = VotingPeriod.query.order_by(VotingPeriod.start_date.desc()).all()
    active_period = VotingPeriod.query.filter_by(is_active=True).first()
    now = datetime.now()  
    return render_template('admin/dashboard.html',
                          user_count=user_count,
                          video_count=video_count,
                          vote_count=vote_count,
                          blacklist_count=blacklist_count,
                          voting_periods=voting_periods,
                          active_period=active_period,
                          now=now)
@admin_bp.route('/blacklist')
@login_required
@admin_required
def blacklist():
    blacklisted = BlacklistedCreator.query.join(Creator).all()
    creators = Creator.query.all()
    return render_template('admin/blacklist.html', blacklisted=blacklisted, creators=creators)
@admin_bp.route('/blacklist/add', methods=['POST'])
@login_required
@admin_required
def add_to_blacklist():
    creator_id = request.form.get('creator_id')
    reason = request.form.get('reason', '')
    if not creator_id:
        flash("No creator selected.", "danger")
        return redirect(url_for('admin.blacklist'))
    creator = Creator.query.get(creator_id)
    if not creator:
        flash("Creator not found.", "danger")
        return redirect(url_for('admin.blacklist'))
    existing = BlacklistedCreator.query.filter_by(creator_id=creator_id).first()
    if existing:
        flash(f"{creator.name} is already blacklisted.", "warning")
        return redirect(url_for('admin.blacklist'))
    blacklist_entry = BlacklistedCreator(creator_id=creator_id, reason=reason)
    db.session.add(blacklist_entry)
    db.session.commit()
    flash(f"{creator.name} has been added to the blacklist.", "success")
    return redirect(url_for('admin.blacklist'))
@admin_bp.route('/blacklist/remove/<int:id>', methods=['POST'])
@login_required
@admin_required
def remove_from_blacklist(id):
    blacklist_entry = BlacklistedCreator.query.get_or_404(id)
    creator_name = blacklist_entry.creator.name
    db.session.delete(blacklist_entry)
    db.session.commit()
    flash(f"{creator_name} has been removed from the blacklist.", "success")
    return redirect(url_for('admin.blacklist'))
@admin_bp.route('/voting-periods')
@login_required
@admin_required
def voting_periods():
    periods = VotingPeriod.query.order_by(VotingPeriod.start_date.desc()).all()
    now = datetime.now()  
    return render_template('admin/voting_periods.html', periods=periods, now=now)
@admin_bp.route('/voting-periods/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_voting_period():
    if request.method == 'POST':
        name = request.form.get('name')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        is_active = request.form.get('is_active') == 'on'
        use_weighted_points = request.form.get('use_weighted_points') == 'on'
        if not name or not start_date_str or not end_date_str:
            flash("All fields are required.", "danger")
            return redirect(url_for('admin.create_voting_period'))
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            if end_date <= start_date:
                flash("End date must be after start date.", "danger")
                return redirect(url_for('admin.create_voting_period'))
            if is_active:
                VotingPeriod.query.filter_by(is_active=True).update({VotingPeriod.is_active: False})
            new_period = VotingPeriod(
                name=name,
                start_date=start_date,
                end_date=end_date,
                is_active=is_active,
                use_weighted_points=use_weighted_points
            )
            db.session.add(new_period)
            db.session.commit()
            flash(f"Voting period '{name}' has been created.", "success")
            return redirect(url_for('admin.voting_periods'))
        except ValueError:
            flash("Invalid date format. Use YYYY-MM-DD.", "danger")
            return redirect(url_for('admin.create_voting_period'))
    now = datetime.now()  
    return render_template('admin/create_voting_period.html', now=now)
@admin_bp.route('/voting-periods/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_voting_period(id):
    period = VotingPeriod.query.get_or_404(id)
    if request.method == 'POST':
        name = request.form.get('name')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        is_active = request.form.get('is_active') == 'on'
        use_weighted_points = request.form.get('use_weighted_points') == 'on'
        if not name or not start_date_str or not end_date_str:
            flash("All fields are required.", "danger")
            return redirect(url_for('admin.edit_voting_period', id=id))
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            if end_date <= start_date:
                flash("End date must be after start date.", "danger")
                return redirect(url_for('admin.edit_voting_period', id=id))
            if is_active and not period.is_active:
                VotingPeriod.query.filter_by(is_active=True).update({VotingPeriod.is_active: False})
            period.name = name
            period.start_date = start_date
            period.end_date = end_date
            period.is_active = is_active
            period.use_weighted_points = use_weighted_points
            db.session.commit()
            flash(f"Voting period '{name}' has been updated.", "success")
            return redirect(url_for('admin.voting_periods'))
        except ValueError:
            flash("Invalid date format. Use YYYY-MM-DD.", "danger")
            return redirect(url_for('admin.edit_voting_period', id=id))
    now = datetime.now()  
    return render_template('admin/edit_voting_period.html', period=period, now=now)
@admin_bp.route('/voting-periods/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_voting_period(id):
    period = VotingPeriod.query.get_or_404(id)
    vote_count = Vote.query.filter_by(voting_period_id=id).count()
    if vote_count > 0:
        flash(f"Cannot delete period '{period.name}' because it has {vote_count} votes associated with it.", "danger")
        return redirect(url_for('admin.voting_periods'))
    period_name = period.name
    db.session.delete(period)
    db.session.commit()
    flash(f"Voting period '{period_name}' has been deleted.", "success")
    return redirect(url_for('admin.voting_periods'))
@admin_bp.route('/users')
@login_required
@admin_required
def users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)
@admin_bp.route('/users/<int:id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash("You cannot change your own admin status.", "danger")
        return redirect(url_for('admin.users'))
    user.is_admin = not user.is_admin
    db.session.commit()
    action = "granted" if user.is_admin else "revoked"
    flash(f"Admin privileges {action} for {user.username}.", "success")
    return redirect(url_for('admin.users'))
@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    if request.method == 'POST':
        test_mode = request.form.get('test_mode') == 'on'
        admin_discord_ids = request.form.get('admin_discord_ids', '')
        admin_discord_ids = [id.strip() for id in admin_discord_ids.split(',') if id.strip()]
        test_username = request.form.get('test_username')
        test_email = request.form.get('test_email')
        test_is_admin = request.form.get('test_is_admin') == 'on'
        show_standalone_playlists = request.form.get('show_standalone_playlists') == 'on'
        enable_historical_playlists = request.form.get('enable_historical_playlists') == 'on'
        historical_playlist_spreadsheet_url = request.form.get('historical_playlist_spreadsheet_url')
        Config.TEST_MODE = test_mode
        Config.ADMIN_DISCORD_IDS = admin_discord_ids
        Config.TEST_USER = {
            'username': test_username or 'TestUser',
            'email': test_email or 'test@example.com',
            'is_admin': test_is_admin
        }
        Config.SHOW_STANDALONE_PLAYLISTS = show_standalone_playlists
        Config.ENABLE_HISTORICAL_PLAYLISTS = enable_historical_playlists
        Config.HISTORICAL_PLAYLIST_SPREADSHEET_URL = historical_playlist_spreadsheet_url
        Config.save_to_file()
        current_app.config['TEST_MODE'] = Config.TEST_MODE
        current_app.config['ADMIN_DISCORD_IDS'] = Config.ADMIN_DISCORD_IDS
        current_app.config['TEST_USER'] = Config.TEST_USER
        flash("Settings updated successfully.", "success")
        return redirect(url_for('admin.settings'))
    admin_discord_ids = ', '.join(Config.ADMIN_DISCORD_IDS)
    test_user = {
        'username': Config.TEST_USER.get('username', 'TestUser'),
        'email': Config.TEST_USER.get('email', 'test@example.com'),
        'is_admin': Config.TEST_USER.get('is_admin', True)
    }
    return render_template('admin/settings.html',
                          test_mode=Config.TEST_MODE,
                          test_user=test_user,
                          admin_discord_ids=admin_discord_ids,
                          show_standalone_playlists=Config.SHOW_STANDALONE_PLAYLISTS,
                          enable_historical_playlists=Config.ENABLE_HISTORICAL_PLAYLISTS,
                          historical_playlist_spreadsheet_url=Config.HISTORICAL_PLAYLIST_SPREADSHEET_URL)
@admin_bp.route('/results')
@login_required
@admin_required
def results():
    periods = VotingPeriod.query.order_by(VotingPeriod.start_date.desc()).all()
    period_id = request.args.get('period_id', type=int)
    if not period_id:
        now = datetime.now()
        completed_period = VotingPeriod.query.filter(VotingPeriod.end_date < now).order_by(VotingPeriod.end_date.desc()).first()
        if completed_period:
            period_id = completed_period.id
        elif periods:
            period_id = periods[0].id
    selected_period = None
    results_data = []
    if period_id:
        selected_period = VotingPeriod.query.get_or_404(period_id)
        if selected_period.use_weighted_points:
            point_formula = 11 - Vote.rank
        else:
            point_formula = 1
        results = db.session.query(
            Video,
            func.count(Vote.id).label('vote_count'),
            func.sum(point_formula).label('total_points')
        ).join(Vote).filter(
            Vote.voting_period_id == period_id
        ).group_by(Video.id).order_by(
            desc('total_points'), desc('vote_count')
        ).all()
        for i, (video, vote_count, total_points) in enumerate(results, 1):
            results_data.append({
                'rank': i,
                'video': video,
                'creator': video.creator,
                'vote_count': vote_count,
                'total_points': total_points
            })
    playlists = []
    if selected_period:
        playlists = Playlist.query.filter_by(voting_period_id=selected_period.id).all()
    return render_template('admin/results.html', 
                           periods=periods,
                           selected_period=selected_period,
                           results=results_data,
                           playlists=playlists)
@admin_bp.route('/results/<int:period_id>/export')
@login_required
@admin_required
def export_results(period_id):
    period = VotingPeriod.query.get_or_404(period_id)
    if period.use_weighted_points:
        point_formula = 11 - Vote.rank
    else:
        point_formula = 1
    results = db.session.query(
        Video,
        func.count(Vote.id).label('vote_count'),
        func.sum(point_formula).label('total_points')
    ).join(Vote).filter(
        Vote.voting_period_id == period_id
    ).group_by(Video.id).order_by(
        desc('total_points'), desc('vote_count')
    ).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Rank', 'Title', 'Creator', 'URL', 'Vote Count', 'Total Points'])
    for i, (video, vote_count, total_points) in enumerate(results, 1):
        writer.writerow([
            i,
            video.title,
            video.creator.name,
            video.url,
            vote_count,
            total_points
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=top_ten_pony_{period.name.replace(' ', '_')}.csv"}
    )
@admin_bp.route('/results/<int:period_id>/votes/export')
@login_required
@admin_required
def export_votes(period_id):
    period = VotingPeriod.query.get_or_404(period_id)
    votes = db.session.query(
        User.username,
        Vote.rank,
        Video.title,
        Video.url,
        Creator.name.label('creator_name'),
        Vote.created_at
    ).join(User, User.id == Vote.user_id
    ).join(Video, Video.id == Vote.video_id
    ).join(Creator, Creator.id == Video.creator_id
    ).filter(Vote.voting_period_id == period_id
    ).order_by(User.username, Vote.rank).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Username', 'Rank', 'Video Title', 'Creator', 'URL', 'Vote Date'])
    for vote in votes:
        writer.writerow([
            vote.username,
            vote.rank,
            vote.title,
            vote.creator_name,
            vote.url,
            vote.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=votes_{period.name.replace(' ', '_')}.csv"}
    )
@admin_bp.route('/historical-playlists/import', methods=['GET', 'POST'])
@login_required
@admin_required
def import_historical_playlists_old():
    if not Config.ENABLE_HISTORICAL_PLAYLISTS:
        flash("Historical playlists feature is not enabled in settings.", "warning")
        return redirect(url_for('admin.settings'))
    if not Config.HISTORICAL_PLAYLIST_SPREADSHEET_URL:
        flash("No Google Spreadsheet URL configured for historical playlists.", "warning")
        return redirect(url_for('admin.settings'))
    if request.method == 'POST':
        try:
            service_account_info = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT_INFO', '{}'))
            if not service_account_info:
                flash("Google Service Account credentials not configured.", "danger")
                return redirect(url_for('admin.playlists'))
            spreadsheet_url = Config.HISTORICAL_PLAYLIST_SPREADSHEET_URL
            parsed_url = urlparse(spreadsheet_url)
            if parsed_url.netloc != 'docs.google.com':
                flash("Invalid Google Spreadsheet URL.", "danger")
                return redirect(url_for('admin.playlists'))
            path_parts = parsed_url.path.strip('/').split('/')
            if len(path_parts) < 2 or path_parts[0] != 'spreadsheets' and path_parts[0] != 'd':
                spreadsheet_id = path_parts[1]
            else:
                spreadsheet_id = path_parts[2]
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
            gc = gspread.authorize(credentials)
            spreadsheet = gc.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.get_worksheet(0)  
            records = worksheet.get_all_records()
            if not records:
                flash("No data found in the spreadsheet.", "warning")
                return redirect(url_for('admin.playlists'))
            playlists_data = {}
            for record in records:
                if 'Year' not in record or 'Month' not in record or 'Video Link' not in record:
                    continue
                if not record['Year'] or not record['Month'] or not record['Video Link']:
                    continue
                year = int(record['Year'])
                month = int(record['Month'])
                key = f"{year}-{month:02d}"
                if key not in playlists_data:
                    playlists_data[key] = {
                        'year': year,
                        'month': month,
                        'entries': []
                    }
                rank = None
                for field in record:
                    if field.lower() in ('rank', 'position'):
                        if record[field] and str(record[field]).isdigit():
                            rank = int(record[field])
                            break
                if not rank:
                    rank = len(playlists_data[key]['entries']) + 1
                entry = {
                    'rank': rank,
                    'video_link': record['Video Link'],
                    'title': record.get('Title', ''),
                    'creator': record.get('Creator', ''),
                    'platform': record.get('Platform', 'YouTube')
                }
                playlists_data[key]['entries'].append(entry)
            imported_count = 0
            skipped_count = 0
            error_count = 0
            for key, data in playlists_data.items():
                month_name = datetime(2000, data['month'], 1).strftime('%B')
                playlist_name = f"Top Ten Pony Videos - {month_name} {data['year']}"
                existing_playlist = Playlist.query.filter_by(
                    year=data['year'], 
                    month=data['month'],
                    is_historical=True
                ).first()
                if existing_playlist:
                    skipped_count += 1
                    continue
                new_playlist = Playlist(
                    name=playlist_name,
                    description=f"Historical Top Ten Pony Videos from {month_name} {data['year']}. Imported from spreadsheet archive.",
                    is_public=True,
                    is_historical=True,
                    year=data['year'],
                    month=data['month']
                )
                db.session.add(new_playlist)
                db.session.flush()  
                entries = sorted(data['entries'], key=lambda x: x['rank'])
                for position, entry in enumerate(entries):
                    try:
                        item = PlaylistItem(
                            playlist_id=new_playlist.id,
                            custom_url=entry['video_link'],
                            custom_title=entry['title'] or f"Historical video {data['year']}-{data['month']}",
                            custom_creator=entry['creator'],
                            custom_platform=entry['platform'],
                            position=position
                        )
                        db.session.add(item)
                    except Exception as e:
                        error_count += 1
                        continue
                imported_count += 1
            db.session.commit()
            if imported_count > 0:
                flash(f"Successfully imported {imported_count} historical playlists. Skipped {skipped_count} existing playlists. Encountered {error_count} errors.", "success")
            else:
                flash(f"No new historical playlists were imported. Skipped {skipped_count} existing playlists.", "info")
            return redirect(url_for('admin.playlists'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error importing historical playlists: {str(e)}", "danger")
            return redirect(url_for('admin.playlists'))
    return render_template('admin/import_historical_playlists.html',
                          spreadsheet_url=Config.HISTORICAL_PLAYLIST_SPREADSHEET_URL)
@admin_bp.route('/playlists')
@login_required
@admin_required
def playlists():
    playlists = Playlist.query.order_by(Playlist.created_at.desc()).all()
    periods = VotingPeriod.query.order_by(VotingPeriod.start_date.desc()).all()
    return render_template('admin/playlists.html', playlists=playlists, periods=periods)
@admin_bp.route('/playlists/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_playlist():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        is_standalone = 'is_standalone' in request.form
        is_public = 'is_public' in request.form
        voting_period_id = None if is_standalone else request.form.get('voting_period_id', type=int)
        if not name:
            flash("Playlist name is required.", "danger")
            return redirect(url_for('admin.create_playlist'))
        if not is_standalone and not voting_period_id:
            flash("Voting period is required for non-standalone playlists.", "danger")
            return redirect(url_for('admin.create_playlist'))
        playlist = Playlist(
            name=name,
            description=description,
            voting_period_id=voting_period_id,
            is_public=is_public
        )
        db.session.add(playlist)
        db.session.commit()
        flash(f"Playlist '{name}' has been created.", "success")
        return redirect(url_for('admin.edit_playlist', id=playlist.id))
    periods = VotingPeriod.query.order_by(VotingPeriod.start_date.desc()).all()
    return render_template('admin/create_playlist.html', periods=periods)
@admin_bp.route('/playlists/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_playlist(id):
    playlist = Playlist.query.get_or_404(id)
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        is_standalone = 'is_standalone' in request.form
        is_public = 'is_public' in request.form
        voting_period_id = None if is_standalone else request.form.get('voting_period_id', type=int)
        if not name:
            flash("Playlist name is required.", "danger")
            return redirect(url_for('admin.edit_playlist', id=id))
        if not is_standalone and not voting_period_id:
            flash("Voting period is required for non-standalone playlists.", "danger")
            return redirect(url_for('admin.edit_playlist', id=id))
        playlist.name = name
        playlist.description = description
        playlist.voting_period_id = voting_period_id
        playlist.is_public = is_public
        playlist.updated_at = datetime.now()
        db.session.commit()
        flash(f"Playlist '{name}' has been updated.", "success")
        return redirect(url_for('admin.playlists'))
    periods = VotingPeriod.query.order_by(VotingPeriod.start_date.desc()).all()
    return render_template('admin/edit_playlist.html', playlist=playlist, periods=periods)
@admin_bp.route('/playlists/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_playlist(id):
    playlist = Playlist.query.get_or_404(id)
    name = playlist.name
    db.session.delete(playlist)
    db.session.commit()
    flash(f"Playlist '{name}' has been deleted.", "success")
    return redirect(url_for('admin.playlists'))
@admin_bp.route('/playlists/<int:id>/items', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_playlist_items(id):
    playlist = Playlist.query.get_or_404(id)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_video':
            video_id = request.form.get('video_id', type=int)
            position = request.form.get('position', type=int) or (len(playlist.items) + 1)
            if video_id:
                video = Video.query.get_or_404(video_id)
                existing = PlaylistItem.query.filter_by(playlist_id=id, video_id=video_id).first()
                if existing:
                    flash(f"Video '{video.title}' is already in this playlist.", "warning")
                    return redirect(url_for('admin.manage_playlist_items', id=id))
                item = PlaylistItem(
                    playlist_id=id,
                    video_id=video_id,
                    position=position
                )
                db.session.add(item)
                db.session.commit()
                flash(f"Video '{video.title}' has been added to the playlist.", "success")
        elif action == 'add_custom':
            url = request.form.get('url')
            title = request.form.get('title')
            position = request.form.get('custom_position', type=int) or (len(playlist.items) + 1)
            if url and title:
                item = PlaylistItem(
                    playlist_id=id,
                    custom_url=url,
                    custom_title=title,
                    position=position
                )
                db.session.add(item)
                db.session.commit()
                flash(f"Custom video '{title}' has been added to the playlist.", "success")
        elif action == 'reorder':
            item_ids = request.form.getlist('item_id[]')
            positions = request.form.getlist('position[]')
            if len(item_ids) == len(positions):
                for item_id, position in zip(item_ids, positions):
                    item = PlaylistItem.query.get(int(item_id))
                    if item and item.playlist_id == id:
                        item.position = int(position)
                db.session.commit()
                flash("Playlist order has been updated.", "success")
        return redirect(url_for('admin.manage_playlist_items', id=id))
    playlist_items = PlaylistItem.query.filter_by(playlist_id=id).order_by(PlaylistItem.position).all()
    available_videos = []
    if playlist.voting_period_id:
        voting_period = VotingPeriod.query.get(playlist.voting_period_id)
        if voting_period and voting_period.use_weighted_points:
            point_formula = 11 - Vote.rank
        else:
            point_formula = 1
        top_videos = db.session.query(
            Video,
            func.count(Vote.id).label('vote_count'),
            func.sum(point_formula).label('total_points')
        ).join(Vote).filter(
            Vote.voting_period_id == playlist.voting_period_id
        ).group_by(Video.id).order_by(
            desc('total_points'), desc('vote_count')
        ).limit(20).all()
        existing_video_ids = [item.video_id for item in playlist_items if item.video_id]
        available_videos = [(v[0].id, v[0].title, v[0].creator.name) for v in top_videos 
                           if v[0].id not in existing_video_ids]
    else:
        recent_videos = Video.query.order_by(Video.created_at.desc()).limit(20).all()
        existing_video_ids = [item.video_id for item in playlist_items if item.video_id]
        available_videos = [(v.id, v.title, v.creator.name) for v in recent_videos 
                           if v.id not in existing_video_ids]
    return render_template('admin/manage_playlist_items.html', 
                           playlist=playlist, 
                           items=playlist_items,
                           available_videos=available_videos)
@admin_bp.route('/playlists/<int:playlist_id>/items/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
@admin_required
def delete_playlist_item(playlist_id, item_id):
    item = PlaylistItem.query.filter_by(id=item_id, playlist_id=playlist_id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    remaining_items = PlaylistItem.query.filter_by(playlist_id=playlist_id).order_by(PlaylistItem.position).all()
    for i, item in enumerate(remaining_items, 1):
        item.position = i
    db.session.commit()
    flash("Item removed from playlist.", "success")
    return redirect(url_for('admin.manage_playlist_items', id=playlist_id))
@admin_bp.route('/playlists/<int:playlist_id>/add-item', methods=['POST'])
@login_required
@admin_required
def add_playlist_item(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    video_id = request.form.get('video_id', type=int)
    if not video_id:
        flash("No video selected.", "danger")
        return redirect(url_for('admin.manage_playlist_items', id=playlist_id))
    video = Video.query.get_or_404(video_id)
    existing = PlaylistItem.query.filter_by(playlist_id=playlist_id, video_id=video_id).first()
    if existing:
        flash(f"Video '{video.title}' is already in this playlist.", "warning")
        return redirect(url_for('admin.manage_playlist_items', id=playlist_id))
    position = PlaylistItem.query.filter_by(playlist_id=playlist_id).count() + 1
    item = PlaylistItem(
        playlist_id=playlist_id,
        video_id=video_id,
        position=position
    )
    db.session.add(item)
    db.session.commit()
    flash(f"Added '{video.title}' to the playlist.", "success")
    return redirect(url_for('admin.manage_playlist_items', id=playlist_id))
@admin_bp.route('/playlists/<int:playlist_id>/add-custom', methods=['POST'])
@login_required
@admin_required
def add_custom_item(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    custom_title = request.form.get('custom_title')
    custom_url = request.form.get('custom_url')
    custom_thumbnail_url = request.form.get('custom_thumbnail_url')
    custom_creator = request.form.get('custom_creator')
    custom_platform = request.form.get('custom_platform')
    custom_duration_seconds = request.form.get('custom_duration_seconds', type=int)
    custom_upload_date_str = request.form.get('custom_upload_date')
    position = request.form.get('position', type=int)
    if not custom_title or not custom_url:
        flash("Title and URL are required for custom videos.", "danger")
        return redirect(url_for('admin.manage_playlist_items', id=playlist_id))
    if not position:
        position = PlaylistItem.query.filter_by(playlist_id=playlist_id).count() + 1
    custom_upload_date = None
    if custom_upload_date_str:
        try:
            custom_upload_date = datetime.strptime(custom_upload_date_str, '%Y-%m-%d')
        except ValueError:
            pass
    item = PlaylistItem(
        playlist_id=playlist_id,
        custom_title=custom_title,
        custom_url=custom_url,
        custom_thumbnail_url=custom_thumbnail_url,
        custom_creator=custom_creator,
        custom_platform=custom_platform,
        custom_duration_seconds=custom_duration_seconds,
        custom_upload_date=custom_upload_date,
        position=position
    )
    db.session.add(item)
    db.session.commit()
    flash(f"Added custom video '{custom_title}' to the playlist.", "success")
    return redirect(url_for('admin.manage_playlist_items', id=playlist_id))
@admin_bp.route('/fetch-video-metadata', methods=['POST'])
@login_required
@admin_required
def fetch_video_metadata():
    from video_utils import VideoExtractor
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'success': False, 'error': 'No URL provided'})
    url = data['url']
    try:
        video_info = VideoExtractor.extract_video_info(url)
        return jsonify({
            'success': True,
            'title': video_info.get('title'),
            'thumbnail_url': video_info.get('thumbnail_url'),
            'platform': video_info.get('platform'),
            'creator': video_info.get('creator_name'),
            'duration_seconds': video_info.get('duration_seconds'),
            'upload_date': video_info.get('upload_date')
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching video metadata: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
@admin_bp.route('/playlists/<int:playlist_id>/add-top', methods=['POST'])
@login_required
@admin_required
def add_top_videos(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    top_count = request.form.get('top_count', type=int) or 10
    replace_existing = request.form.get('replace_existing') == 'true'
    if top_count > 50:
        top_count = 50
    if replace_existing:
        PlaylistItem.query.filter_by(playlist_id=playlist_id).delete()
        db.session.commit()
    videos_to_add = []
    if playlist.voting_period_id:
        voting_period = VotingPeriod.query.get(playlist.voting_period_id)
        if voting_period and voting_period.use_weighted_points:
            point_formula = 11 - Vote.rank
        else:
            point_formula = 1
        top_videos = db.session.query(
            Video,
            func.sum(point_formula).label('total_points')
        ).join(Vote).filter(
            Vote.voting_period_id == playlist.voting_period_id
        ).group_by(Video.id).order_by(
            desc('total_points')
        ).limit(top_count).all()
        videos_to_add = [video for video, _ in top_videos]
    else:
        recent_votes = Vote.query.order_by(Vote.created_at.desc()).limit(1000).all()
        video_votes = {}
        for vote in recent_votes:
            if vote.video_id not in video_votes:
                video_votes[vote.video_id] = 0
            video_votes[vote.video_id] += 1
        top_video_ids = sorted(video_votes.items(), key=lambda x: x[1], reverse=True)[:top_count]
        videos_to_add = []
        for video_id, _ in top_video_ids:
            video = Video.query.get(video_id)
            if video:
                videos_to_add.append(video)
        if len(videos_to_add) < top_count:
            count_to_add = top_count - len(videos_to_add)
            existing_ids = {v.id for v in videos_to_add}
            recent_videos = Video.query.order_by(Video.created_at.desc()).limit(count_to_add*2).all()
            for video in recent_videos:
                if video.id not in existing_ids and len(videos_to_add) < top_count:
                    videos_to_add.append(video)
                    existing_ids.add(video.id)
    start_position = 1
    if not replace_existing:
        start_position = db.session.query(func.max(PlaylistItem.position)).filter_by(playlist_id=playlist_id).scalar() or 0
        start_position += 1
    added_count = 0
    for i, video in enumerate(videos_to_add, start_position):
        if not replace_existing:
            existing = PlaylistItem.query.filter_by(playlist_id=playlist_id, video_id=video.id).first()
            if existing:
                continue
        item = PlaylistItem(
            playlist_id=playlist_id,
            video_id=video.id,
            position=i
        )
        db.session.add(item)
        added_count += 1
    db.session.commit()
    flash(f"Added {added_count} top videos to the playlist.", "success")
    return redirect(url_for('admin.manage_playlist_items', id=playlist_id))
@admin_bp.route('/playlists/<int:id>/update-positions', methods=['POST'])
@login_required
@admin_required
def update_playlist_positions(id):
    playlist = Playlist.query.get_or_404(id)
    data = request.json
    if not data or 'items' not in data:
        return jsonify({'success': False, 'error': 'Invalid data format'})
    try:
        for item_data in data['items']:
            item_id = item_data.get('id')
            position = item_data.get('position')
            if not item_id or not position:
                print("Invalid item data:", item_data)
                continue
            item = PlaylistItem.query.get(item_id)
            if item and item.playlist_id == id:
                item.position = position
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})
@admin_bp.route('/historical-settings', methods=['GET', 'POST'])
@login_required
@admin_required
def historical_playlist_settings():
    from models import HistoricalPlaylistSettings
    settings = HistoricalPlaylistSettings.query.first()
    if not settings:
        settings = HistoricalPlaylistSettings()
        db.session.add(settings)
        db.session.commit()
    if request.method == 'POST':
        settings.max_playlists = request.form.get('max_playlists', type=int) or 10
        settings.spreadsheet_id = request.form.get('spreadsheet_id', '').strip()
        settings.worksheet_name = request.form.get('worksheet_name', '').strip() or 'Sheet1'
        settings.auto_import_enabled = 'auto_import_enabled' in request.form
        import_limit_year = request.form.get('import_limit_year', type=int)
        import_limit_month = request.form.get('import_limit_month', type=int)
        settings.import_limit_year = import_limit_year
        settings.import_limit_month = import_limit_month
        next_import_date = request.form.get('next_scheduled_import')
        if next_import_date:
            try:
                settings.next_scheduled_import = datetime.strptime(next_import_date, '%Y-%m-%d')
            except ValueError:
                flash("Invalid date format for next scheduled import.", "warning")
        db.session.commit()
        flash("Historical playlist settings updated successfully.", "success")
        if 'import_now' in request.form:
            return redirect(url_for('admin.import_historical_playlists_new'))
        return redirect(url_for('admin.historical_playlist_settings'))
    historical_count = Playlist.query.filter_by(is_historical=True).count()
    return render_template('admin/historical_settings.html', 
                          settings=settings,
                          historical_count=historical_count)
@admin_bp.route('/historical-import', methods=['GET', 'POST'])
@login_required
@admin_required
def import_historical_playlists_new():
    from models import HistoricalPlaylistSettings
    from video_utils import VideoExtractor
    settings = HistoricalPlaylistSettings.query.first()
    if not settings or not settings.spreadsheet_id:
        flash("Please configure historical playlist settings first.", "warning")
        return redirect(url_for('admin.historical_playlist_settings'))
    results = {
        'total_playlists': 0,
        'successful_imports': 0,
        'failed_imports': 0,
        'skipped_imports': 0,
        'details': []
    }
    if request.method == 'POST':
        try:
            try:
                credentials_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_INFO')
                if credentials_json:
                    try:
                        credentials_info = json.loads(credentials_json)
                        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
                        client = gspread.authorize(credentials)
                        spreadsheet = client.open_by_key(settings.spreadsheet_id)
                        worksheet = spreadsheet.worksheet(settings.worksheet_name)
                        results['details'].append("Successfully accessed spreadsheet using service account credentials")
                    except json.JSONDecodeError:
                        raise Exception("Invalid Google Service Account credentials format")
                else:
                    import requests
                    public_url = f"https://docs.google.com/spreadsheets/d/{settings.spreadsheet_id}/export?format=csv"
                    response = requests.get(public_url)
                    if response.status_code != 200:
                        raise Exception(f"Cannot access spreadsheet: HTTP status {response.status_code}")
                    import csv
                    from io import StringIO
                    csv_data = StringIO(response.text)
                    reader = csv.reader(csv_data)
                    all_data = list(reader)
                    header = all_data[0]  
                    all_data = all_data[1:]  
                    class FakeWorksheet:
                        def get_all_values(self):
                            return [header] + all_data
                    worksheet = FakeWorksheet()
                    results['details'].append("Successfully accessed spreadsheet using public export URL")
            except Exception as e:
                flash(f"Error accessing Google Spreadsheet: {str(e)}", "danger")
                results['details'].append(f"Error: {str(e)}")
                return render_template('admin/import_historical_playlists.html', results=results)
            all_data = worksheet.get_all_values()
            if len(all_data) > 0:
                all_data = all_data[1:]
            playlists_data = {}
            for row in all_data:
                if len(row) < 4:  
                    continue
                try:
                    year = int(row[0])
                    month = int(row[1])
                    rank = int(row[2])
                    video_url = row[3].strip()
                    status = row[7] if len(row) > 7 else ""
                    alt_url = row[8] if len(row) > 8 else ""
                    if settings.import_limit_year and year < settings.import_limit_year:
                        continue
                    if settings.import_limit_year and settings.import_limit_month and year == settings.import_limit_year and month < settings.import_limit_month:
                        continue
                    if not video_url and not alt_url:
                        continue
                    if status and alt_url:
                        video_url = alt_url
                    period_key = f"{year}-{month:02d}"
                    if period_key not in playlists_data:
                        playlists_data[period_key] = {
                            'year': year,
                            'month': month,
                            'videos': []
                        }
                    playlists_data[period_key]['videos'].append({
                        'rank': rank,
                        'url': video_url
                    })
                except (ValueError, IndexError) as e:
                    results['details'].append(f"Skipped row: {e}")
                    continue
            sorted_periods = sorted(playlists_data.items(), key=lambda x: (x[1]['year'], x[1]['month']), reverse=True)
            if settings.max_playlists:
                sorted_periods = sorted_periods[:settings.max_playlists]
            results['total_playlists'] = len(sorted_periods)
            for period_key, period_data in sorted_periods:
                year = period_data['year']
                month = period_data['month']
                videos = period_data['videos']
                videos.sort(key=lambda x: x['rank'])
                existing = Playlist.query.filter_by(is_historical=True, year=year, month=month).first()
                if existing:
                    playlist = existing
                    PlaylistItem.query.filter_by(playlist_id=playlist.id).delete()
                    results['details'].append(f"Updating existing playlist for {year}-{month:02d}")
                else:
                    month_name = ['January', 'February', 'March', 'April', 'May', 'June', 
                                  'July', 'August', 'September', 'October', 'November', 'December'][month-1]
                    playlist = Playlist(
                        name=f"Top Ten: {month_name} {year}",
                        description=f"Historical Top Ten playlist from {month_name} {year}.",
                        is_historical=True,
                        year=year,
                        month=month,
                        is_public=True
                    )
                    db.session.add(playlist)
                    db.session.flush()  
                    results['details'].append(f"Created new playlist for {year}-{month:02d}")
                position = 1
                for video_data in videos:
                    try:
                        video_info = VideoExtractor.extract_video_info(video_data['url'])
                        creator = Creator.query.filter_by(name=video_info['creator_name']).first()
                        if not creator:
                            creator = Creator(name=video_info['creator_name'])
                            db.session.add(creator)
                            db.session.flush()
                        video = Video.query.filter_by(
                            platform=video_info['platform'],
                            video_id=video_info['video_id']
                        ).first()
                        if not video:
                            video = Video(
                                title=video_info['title'],
                                platform=video_info['platform'],
                                video_id=video_info['video_id'],
                                url=video_info['url'],
                                thumbnail_url=video_info.get('thumbnail_url'),
                                duration_seconds=video_info.get('duration_seconds'),
                                creator_id=creator.id,
                                similarity_hash=VideoExtractor.generate_similarity_hash(video_info)
                            )
                            upload_date = video_info.get('upload_date')
                            if upload_date:
                                if isinstance(upload_date, str):
                                    try:
                                        upload_date = datetime.strptime(upload_date, '%Y%m%d')
                                    except ValueError:
                                        upload_date = None
                                video.upload_date = upload_date
                            db.session.add(video)
                            db.session.flush()
                        item = PlaylistItem(
                            playlist_id=playlist.id,
                            video_id=video.id,
                            position=position
                        )
                        db.session.add(item)
                        position += 1
                    except Exception as e:
                        error_msg = str(e)
                        if "age-restricted" in error_msg.lower():
                            error_type = "Age-restricted video"
                        elif "private video" in error_msg.lower():
                            error_type = "Private video"
                        elif "copyright" in error_msg.lower():
                            error_type = "Copyright claim"
                        elif "not available" in error_msg.lower():
                            error_type = "Video not available"
                        elif "video id" in error_msg.lower():
                            error_type = "Invalid video ID"
                        else:
                            error_type = "Import error"
                        item = PlaylistItem(
                            playlist_id=playlist.id,
                            custom_url=video_data['url'],
                            custom_title=f"Video at rank {video_data['rank']} ({error_type})",
                            custom_platform="unknown",
                            position=position
                        )
                        db.session.add(item)
                        position += 1
                        results['details'].append(f"Error with video at rank {video_data['rank']} in {year}-{month:02d}: {error_type} - {error_msg}")
                if position > 1:
                    results['successful_imports'] += 1
                else:
                    results['failed_imports'] += 1
            db.session.commit()
            settings.last_import_date = datetime.now()
            db.session.commit()
            flash(f"Successfully imported {results['successful_imports']} historical playlists.", "success")
        except Exception as e:
            db.session.rollback()
            error_msg = str(e)
            if "OAuth" in error_msg or "service account" in error_msg.lower():
                error_description = "Google Service Account configuration error. Check your GOOGLE_SERVICE_ACCOUNT_INFO environment variable."
                results['details'].append("Troubleshooting: Verify that the service account has access to the spreadsheet.")
            elif "not found" in error_msg.lower() or "404" in error_msg:
                error_description = "Spreadsheet not found. Check your spreadsheet ID and sharing settings."
                results['details'].append("Troubleshooting: Make sure the spreadsheet is shared with 'Anyone with link' or with your service account email.")
            elif "permission" in error_msg.lower() or "403" in error_msg:
                error_description = "Permission denied accessing the spreadsheet."
                results['details'].append("Troubleshooting: Check sharing permissions and service account access.")
            elif "YouTube API" in error_msg:
                error_description = "YouTube API error. Check your YOUTUBE_API_KEY environment variable."
                results['details'].append("Troubleshooting: Verify your YouTube API key is valid and has YouTube Data API v3 enabled.")
            else:
                error_description = f"Error importing historical playlists: {error_msg}"
            flash(error_description, "danger")
            results['details'].append(f"Fatal error: {error_msg}")
    return render_template('admin/import_historical_playlists.html', results=results)
