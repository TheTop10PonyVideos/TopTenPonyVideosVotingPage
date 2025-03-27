from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort, Response, current_app
from flask_login import current_user, login_required
from app import db
from models import User, Vote, Video, Creator, BlacklistedCreator, VotingPeriod, Playlist, PlaylistItem
from video_utils import validate_video, VideoExtractor, SUPPORTED_PLATFORMS
from auth import admin_required
import logging
import csv
from io import StringIO
from sqlalchemy import func, desc
main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)
@main_bp.route('/')
def index():
    current_period = VotingPeriod.query.filter_by(is_active=True).first()
    top_videos = []
    if current_period and datetime.utcnow() > current_period.end_date:
        video_scores = {}
        votes = Vote.query.filter_by(voting_period_id=current_period.id).all()
        for vote in votes:
            points = 11 - vote.rank
            video_scores[vote.video_id] = video_scores.get(vote.video_id, 0) + points
        top_video_ids = sorted(video_scores.keys(), key=lambda x: video_scores[x], reverse=True)[:10]
        top_videos = []
        for i, video_id in enumerate(top_video_ids):
            video = Video.query.get(video_id)
            if video:
                top_videos.append({
                    'rank': i + 1,
                    'video': video,
                    'score': video_scores[video_id]
                })
    return render_template('index.html', 
                          current_period=current_period, 
                          top_videos=top_videos,
                          current_time=datetime.utcnow())
@main_bp.route('/vote', methods=['GET', 'POST'])
@login_required
def vote():
    current_period = VotingPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        flash("There is no active voting period at this time.", "warning")
        return redirect(url_for('main.index'))
    now = datetime.utcnow()
    if now < current_period.start_date:
        flash(f"Voting will begin on {current_period.start_date.strftime('%Y-%m-%d')}.", "info")
        return redirect(url_for('main.index'))
    if now > current_period.end_date:
        flash("Voting has ended for this period.", "info")
        return redirect(url_for('main.results'))
    user_votes = Vote.query.filter_by(user_id=current_user.id, voting_period_id=current_period.id).all()
    voted_videos = {vote.video_id: vote.rank for vote in user_votes}
    voted_video_objects = Video.query.filter(Video.id.in_(voted_videos.keys())).all() if voted_videos else []
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        try:
            votes = data.get('votes', [])
            if len(votes) < 5 or len(votes) > 10:
                return jsonify({'success': False, 'message': 'You must vote for 5-10 videos'}), 400
            video_ranks = {int(vote['video_id']): int(vote['rank']) for vote in votes}
            videos = Video.query.filter(Video.id.in_(video_ranks.keys())).all()
            if len(videos) != len(video_ranks):
                return jsonify({'success': False, 'message': 'One or more videos not found'}), 400
            if len(votes) <= 5:
                creator_ids = set()
                for video in videos:
                    if video.creator_id in creator_ids:
                        return jsonify({
                            'success': False, 
                            'message': 'When voting for 5 or fewer videos, all videos must be from different creators'
                        }), 400
                    creator_ids.add(video.creator_id)
            Vote.query.filter_by(user_id=current_user.id, voting_period_id=current_period.id).delete()
            for video in videos:
                new_vote = Vote(
                    user_id=current_user.id,
                    video_id=video.id,
                    voting_period_id=current_period.id,
                    rank=video_ranks[video.id]
                )
                db.session.add(new_vote)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Votes submitted successfully'})
        except Exception as e:
            logger.error(f"Error processing votes: {str(e)}")
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    return render_template('vote.html', 
                          current_period=current_period,
                          voted_videos=voted_video_objects,
                          voted_ranks=voted_videos,
                          platforms=SUPPORTED_PLATFORMS)
@main_bp.route('/validate-video', methods=['POST'])
@login_required
def validate_video_url():
    url = request.json.get('url')
    if not url:
        return jsonify({'valid': False, 'message': 'No URL provided'})
    current_period = VotingPeriod.query.filter_by(is_active=True).first()
    if not current_period:
        return jsonify({'valid': False, 'message': 'No active voting period'})
    valid, result = validate_video(url, current_period)
    if not valid:
        return jsonify({'valid': False, 'message': result})
    creator_name = result.get('creator_name')
    blacklisted = BlacklistedCreator.query.join(Creator).filter(Creator.name == creator_name).first()
    if blacklisted:
        return jsonify({'valid': False, 'message': f'Creator "{creator_name}" is blacklisted'})
    existing_video = Video.query.filter_by(url=url).first()
    if existing_video:
        return jsonify({
            'valid': True,
            'video': {
                'id': existing_video.id,
                'title': existing_video.title,
                'platform': existing_video.platform,
                'thumbnail_url': existing_video.thumbnail_url,
                'creator_name': existing_video.creator.name if existing_video.creator else "Unknown"
            }
        })
    similarity_hash = VideoExtractor.generate_similarity_hash(result)
    similar_videos = Video.query.all()  
    for video in similar_videos:
        if VideoExtractor.check_similarity({'title': video.title, 'creator_name': video.creator.name}, 
                                         {'title': result['title'], 'creator_name': result['creator_name']}):
            return jsonify({
                'valid': True,
                'similar': True,
                'original_video': {
                    'id': video.id,
                    'title': video.title,
                    'platform': video.platform,
                    'thumbnail_url': video.thumbnail_url,
                    'creator_name': video.creator.name if video.creator else "Unknown"
                },
                'message': f'This video appears to be the same as "{video.title}" which is already in the system.'
            })
    creator = Creator.query.filter_by(name=result['creator_name']).first()
    if not creator:
        creator = Creator(name=result['creator_name'])
        creator.set_platform_ids({result['platform']: result['creator_id']})
        db.session.add(creator)
        db.session.flush()  
    new_video = Video(
        title=result['title'],
        platform=result['platform'],
        video_id=result['video_id'],
        url=url,
        thumbnail_url=result.get('thumbnail_url'),
        duration_seconds=result.get('duration_seconds', 0),
        upload_date=result.get('upload_date'),
        creator_id=creator.id,
        similarity_hash=similarity_hash
    )
    db.session.add(new_video)
    db.session.commit()
    return jsonify({
        'valid': True,
        'video': {
            'id': new_video.id,
            'title': new_video.title,
            'platform': new_video.platform,
            'thumbnail_url': new_video.thumbnail_url,
            'creator_name': creator.name
        }
    })
@main_bp.route('/results')
def results():
    completed_period = VotingPeriod.query\
        .filter(VotingPeriod.end_date < datetime.utcnow())\
        .order_by(VotingPeriod.end_date.desc())\
        .first()
    if not completed_period:
        flash("No completed voting periods found.", "info")
        return redirect(url_for('main.index'))
    results = []
    votes = Vote.query.filter_by(voting_period_id=completed_period.id).all()
    video_points = {}
    for vote in votes:
        if completed_period.use_weighted_points:
            points = 11 - vote.rank
        else:
            points = 1
        video_points[vote.video_id] = video_points.get(vote.video_id, 0) + points
    ranked_videos = sorted(video_points.items(), key=lambda x: x[1], reverse=True)
    for i, (video_id, points) in enumerate(ranked_videos[:10]):
        video = Video.query.get(video_id)
        if video:
            vote_count = Vote.query.filter_by(voting_period_id=completed_period.id, video_id=video_id).count()
            results.append({
                'rank': i + 1,
                'video': video,
                'points': points,
                'vote_count': vote_count
            })
    return render_template('results.html', period=completed_period, results=results)
@main_bp.route('/votes/export/<int:period_id>')
@login_required
def export_my_votes(period_id):
    period = VotingPeriod.query.get_or_404(period_id)
    if not current_user.is_admin and datetime.utcnow() < period.end_date:
        flash("You can only export your votes after the voting period has ended.", "warning")
        return redirect(url_for('main.vote'))
    user_votes = db.session.query(
        Vote.rank,
        Video.title,
        Video.url,
        Creator.name.label('creator_name'),
        Vote.created_at
    ).join(Video, Video.id == Vote.video_id
    ).join(Creator, Creator.id == Video.creator_id
    ).filter(
        Vote.user_id == current_user.id,
        Vote.voting_period_id == period_id
    ).order_by(Vote.rank).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Rank', 'Video Title', 'Creator', 'URL', 'Vote Date'])
    for vote in user_votes:
        writer.writerow([
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
        headers={"Content-disposition": f"attachment; filename=my_votes_{period.name.replace(' ', '_')}.csv"}
    )
@main_bp.route('/playlists')
@main_bp.route('/playlists/period/<int:period_id>')
def view_playlists(period_id=None):
    completed_periods = VotingPeriod.query\
        .filter(VotingPeriod.end_date < datetime.utcnow())\
        .order_by(VotingPeriod.end_date.desc())\
        .all()
    period = None
    period_playlists = []
    if completed_periods and period_id is not None:
        period = VotingPeriod.query.get_or_404(period_id)
        if datetime.utcnow() < period.end_date:
            flash("This voting period is not yet completed.", "warning")
            return redirect(url_for('main.view_playlists'))
        period_playlists = Playlist.query.filter_by(voting_period_id=period.id, is_public=True).all()
    elif completed_periods:
        period = completed_periods[0]
        period_playlists = Playlist.query.filter_by(voting_period_id=period.id, is_public=True).all()
    standalone_playlists = []
    if current_app.config.get('SHOW_STANDALONE_PLAYLISTS', False):
        standalone_playlists = Playlist.query.filter_by(
            voting_period_id=None, 
            is_public=True, 
            is_historical=False
        ).order_by(Playlist.created_at.desc()).all()
    historical_playlists = []
    if current_app.config.get('ENABLE_HISTORICAL_PLAYLISTS', False):
        historical_playlists = Playlist.query.filter_by(
            is_public=True,
            is_historical=True
        ).order_by(Playlist.year.desc(), Playlist.month.desc()).all()
    playlists = period_playlists + standalone_playlists
    if not playlists and not historical_playlists:
        flash("No playlists are available at this time.", "info")
        return redirect(url_for('main.index'))
    return render_template('playlists.html', 
                          period=period, 
                          playlists=playlists, 
                          standalone_playlists=standalone_playlists,
                          period_playlists=period_playlists,
                          historical_playlists=historical_playlists,
                          voting_periods=completed_periods)
@main_bp.route('/playlists/<int:id>')
def view_playlist(id):
    playlist = Playlist.query.get_or_404(id)
    if not playlist.is_public:
        flash("This playlist is not available.", "warning")
        return redirect(url_for('main.view_playlists'))
    if playlist.voting_period_id and datetime.utcnow() < playlist.voting_period.end_date:
        flash("This playlist is not yet available.", "warning")
        return redirect(url_for('main.view_playlists'))
    related_playlists = []
    if playlist.is_historical:
        if playlist.year and playlist.month:
            related_playlists = Playlist.query\
                .filter(Playlist.is_historical == True,
                        Playlist.year == playlist.year,
                        Playlist.month != playlist.month,
                        Playlist.id != playlist.id,
                        Playlist.is_public == True)\
                .order_by(func.abs(Playlist.month - playlist.month))\
                .limit(3)\
                .all()
            if len(related_playlists) < 3:
                additional_playlists = Playlist.query\
                    .filter(Playlist.is_historical == True,
                            Playlist.year != playlist.year,
                            Playlist.id != playlist.id,
                            Playlist.id.notin_([p.id for p in related_playlists]),
                            Playlist.is_public == True)\
                    .order_by(func.abs(Playlist.year - playlist.year))\
                    .limit(3 - len(related_playlists))\
                    .all()
                related_playlists.extend(additional_playlists)
    elif playlist.voting_period_id:
        related_playlists = Playlist.query\
            .filter(Playlist.voting_period_id == playlist.voting_period_id, 
                    Playlist.id != playlist.id,
                    Playlist.is_public == True)\
            .limit(3)\
            .all()
    else:
        related_playlists = Playlist.query\
            .filter(Playlist.voting_period_id == None,
                    Playlist.is_historical == False,
                    Playlist.id != playlist.id,
                    Playlist.is_public == True)\
            .order_by(Playlist.created_at.desc())\
            .limit(3)\
            .all()
    return render_template('playlist.html', 
                          playlist=playlist, 
                          related_playlists=related_playlists)
