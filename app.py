#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#

from datetime import date, datetime, timedelta, timezone
import json
import os
import re
import secrets
from zoneinfo import ZoneInfo

from authlib.integrations.flask_client import OAuth
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf import CSRFProtect, FlaskForm
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from wtforms import IntegerField
from wtforms.validators import InputRequired, NumberRange

from models import (
    Challenge,
    PuttSequence,
    User,
    WeeklyChallenge,
    WeeklyDraw,
    WeeklyDrawPayout,
    WeeklyEntry,
    db,
)

login_manager = LoginManager()
login_manager.login_view = 'home'
login_manager.login_message = 'Sign in with Google to submit a score.'
oauth = OAuth()
MOUNTAIN_TIME = ZoneInfo('America/Denver')


class ScoreForm(FlaskForm):
    score = IntegerField(
        'Made putts',
        validators=[InputRequired(), NumberRange(min=0, max=20)],
    )


def current_week(now=None):
    now = (now or datetime.now(timezone.utc)).astimezone(MOUNTAIN_TIME)
    monday = (now - timedelta(days=now.weekday())).date()
    return week_key_for(monday), monday


def week_key_for(monday):
    iso_year, iso_week, _ = monday.isocalendar()
    return f'{iso_year}-W{iso_week:02d}'


def competition_ranks(standings):
    total_counts = {}
    for entry in standings:
        total_counts[entry.total] = total_counts.get(entry.total, 0) + 1

    rank_by_user = {}
    tied_user_ids = set()
    for index, entry in enumerate(standings):
        if index and entry.total == standings[index - 1].total:
            rank_by_user[entry.user_id] = rank_by_user[standings[index - 1].user_id]
        else:
            rank_by_user[entry.user_id] = index + 1
        if total_counts[entry.total] > 1:
            tied_user_ids.add(entry.user_id)

    return rank_by_user, tied_user_ids


def ensure_weekly_draw_payouts():
    missing_draw_ids = [
        draw_id
        for (draw_id,) in db.session.query(WeeklyDraw.id)
        .outerjoin(WeeklyDrawPayout, WeeklyDrawPayout.draw_id == WeeklyDraw.id)
        .filter(WeeklyDrawPayout.id.is_(None))
        .all()
    ]
    while missing_draw_ids:
        db.session.add_all(
            WeeklyDrawPayout(draw_id=draw_id) for draw_id in missing_draw_ids
        )
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            remaining_draw_ids = {
                draw_id
                for (draw_id,) in db.session.query(WeeklyDraw.id)
                .outerjoin(WeeklyDrawPayout, WeeklyDrawPayout.draw_id == WeeklyDraw.id)
                .filter(WeeklyDrawPayout.id.is_(None))
                .all()
            }
            if remaining_draw_ids == set(missing_draw_ids):
                raise
            missing_draw_ids = list(remaining_draw_ids)
        else:
            missing_draw_ids = []


def parse_week_key(value):
    if not re.fullmatch(r'\d{4}-W\d{2}', value or ''):
        return None
    try:
        return date.fromisocalendar(int(value[:4]), int(value[6:]), 1)
    except ValueError:
        return None


def analyze_putt_sequence(results):
    longest_streak = 0
    current_streak = 0
    for made in results:
        if made:
            current_streak += 1
            longest_streak = max(longest_streak, current_streak)
        else:
            current_streak = 0

    first_half_makes = sum(results[:10])
    second_half_makes = sum(results[10:])
    if second_half_makes > first_half_makes:
        trend = 'Improved'
    elif second_half_makes < first_half_makes:
        trend = 'Declined'
    else:
        trend = 'Steady'

    segments = [
        {
            'start': start + 1,
            'end': start + 5,
            'made': sum(results[start:start + 5]),
        }
        for start in range(0, 20, 5)
    ]
    return {
        'results': results,
        'segments': segments,
        'first_half_makes': first_half_makes,
        'second_half_makes': second_half_makes,
        'trend': trend,
        'longest_streak': longest_streak,
    }


def finalize_completed_weeks(current_week_key):
    unfinished_weeks = {
        week_key
        for (week_key,) in (
        db.session.query(WeeklyEntry.week_key)
        .outerjoin(WeeklyDraw, WeeklyDraw.week_key == WeeklyEntry.week_key)
        .filter(WeeklyEntry.week_key < current_week_key, WeeklyDraw.id.is_(None))
        .distinct()
        .order_by(WeeklyEntry.week_key)
        .all()
        )
    }
    current_monday = parse_week_key(current_week_key)
    previous_week_key = week_key_for(current_monday - timedelta(days=7))
    if WeeklyDraw.query.filter_by(week_key=previous_week_key).first() is None:
        unfinished_weeks.add(previous_week_key)

    for week_key in sorted(unfinished_weeks):
        entries = WeeklyEntry.query.filter_by(week_key=week_key).all()
        eligible_entries = [entry for entry in entries if entry.score_count == 5]
        winner = secrets.choice(eligible_entries) if eligible_entries else None
        result = WeeklyDraw(
            week_key=week_key,
            winner_name=winner.user.name if winner else None,
            winner_email=winner.user.email if winner else None,
            winner_total=winner.total if winner else None,
            eligible_count=len(eligible_entries),
            drawn_at=datetime.now(timezone.utc),
            payout=WeeklyDrawPayout(),
        )
        db.session.add(result)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if WeeklyDraw.query.filter_by(week_key=week_key).first() is None:
                raise


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object('config')
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    CSRFProtect(app)
    login_manager.init_app(app)
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )

    with app.app_context():
        db.create_all()
        ensure_weekly_draw_payouts()

    def is_admin(user):
        allowed_email = app.config.get('ADMIN_EMAIL', '').strip().casefold()
        return bool(user.is_authenticated and allowed_email and user.email.strip().casefold() == allowed_email)

    @app.context_processor
    def inject_admin_status():
        return {'is_admin': is_admin(current_user)}

    @app.before_request
    def finalize_past_weeks():
        finalize_completed_weeks(current_week()[0])

    @app.get('/')
    def home():
        week_key, week_start = current_week()
        previous_week_start = week_start - timedelta(days=7)
        previous_week_key = week_key_for(previous_week_start)
        scheduled_challenge = WeeklyChallenge.query.filter_by(week_key=week_key).first()
        entries = WeeklyEntry.query.filter_by(week_key=week_key).all()
        standings = sorted(
            entries,
            key=lambda entry: (-entry.total, -entry.score_count, entry.user.name.casefold()),
        )
        rank_by_user, tied_user_ids = competition_ranks(standings)
        previous_entries = WeeklyEntry.query.filter_by(week_key=previous_week_key).all()
        all_previous_standings = sorted(
            previous_entries,
            key=lambda entry: (-entry.total, -entry.score_count, entry.user.name.casefold()),
        )
        previous_rank_by_user, previous_tied_user_ids = competition_ranks(all_previous_standings)
        previous_standings = all_previous_standings[:5]
        previous_draw = WeeklyDraw.query.filter_by(week_key=previous_week_key).first()
        draw_wins = {}
        for winner_email, in WeeklyDraw.query.with_entities(WeeklyDraw.winner_email).filter(
            WeeklyDraw.winner_email.isnot(None)
        ):
            email_key = winner_email.casefold()
            draw_wins[email_key] = draw_wins.get(email_key, 0) + 1
        player_entry = None
        player_rank = None
        if current_user.is_authenticated:
            player_entry = WeeklyEntry.query.filter_by(
                week_key=week_key, user_id=current_user.id
            ).first()
            player_rank = rank_by_user.get(current_user.id)
        form = ScoreForm()
        return render_template(
            'pages/placeholder.home.html',
            week_key=week_key,
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            standings=standings,
            rank_by_user=rank_by_user,
            tied_user_ids=tied_user_ids,
            previous_week_key=previous_week_key,
            previous_standings=previous_standings,
            previous_rank_by_user=previous_rank_by_user,
            previous_tied_user_ids=previous_tied_user_ids,
            previous_draw=previous_draw,
            draw_wins=draw_wins,
            participants=len(entries),
            sessions_total=sum(entry.score_count for entry in entries),
            player_entry=player_entry,
            player_rank=player_rank,
            player_rank_tied=(
                current_user.is_authenticated and current_user.id in tied_user_ids
            ),
            form=form,
            weekly_task=(
                scheduled_challenge.challenge.title
                if scheduled_challenge
                else app.config.get('WEEKLY_TASK', '20 putts from 20 feet')
            ),
            weekly_description=(
                scheduled_challenge.challenge.description if scheduled_challenge else ''
            ),
            google_ready=bool(
                app.config.get('GOOGLE_CLIENT_ID')
                and app.config.get('GOOGLE_CLIENT_SECRET')
            ),
        )

    @app.get('/privacy')
    def privacy():
        return render_template('pages/privacy.html')

    @app.route('/admin', methods=['GET', 'POST'])
    @login_required
    def admin():
        if not is_admin(current_user):
            abort(403)

        ensure_weekly_draw_payouts()

        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'add_challenge':
                title = request.form.get('title', '').strip()
                description = request.form.get('description', '').strip()
                if not title or len(title) > 160 or len(description) > 500:
                    flash('Enter a challenge title (up to 160 characters) and description (up to 500).')
                elif Challenge.query.filter_by(title=title).first():
                    flash('A challenge with that title already exists.')
                else:
                    db.session.add(Challenge(title=title, description=description))
                    db.session.commit()
                    flash('Challenge added.')
                return redirect(url_for('admin'))

            if action == 'schedule_week':
                week_key = request.form.get('week_key', '').strip()
                challenge = db.session.get(Challenge, request.form.get('challenge_id', type=int))
                if parse_week_key(week_key) is None:
                    flash('Enter a valid ISO week, such as 2026-W40.')
                elif challenge is None:
                    flash('Choose an existing challenge.')
                else:
                    assignment = WeeklyChallenge.query.filter_by(week_key=week_key).first()
                    if assignment is None:
                        assignment = WeeklyChallenge(week_key=week_key, challenge=challenge)
                        db.session.add(assignment)
                    else:
                        assignment.challenge = challenge
                    db.session.commit()
                    flash(f'{week_key} is assigned to {challenge.title}.')
                return redirect(url_for('admin'))

            if action == 'delete_user':
                user = db.session.get(User, request.form.get('user_id', type=int))
                if user is None:
                    flash('That user no longer exists.')
                elif user.id == current_user.id:
                    flash('You cannot delete your own admin account here.')
                else:
                    PuttSequence.query.filter(
                        PuttSequence.weekly_entry_id.in_(
                            select(WeeklyEntry.id).where(WeeklyEntry.user_id == user.id)
                        )
                    ).delete(synchronize_session=False)
                    WeeklyEntry.query.filter_by(user_id=user.id).delete(synchronize_session=False)
                    db.session.delete(user)
                    db.session.commit()
                    flash(f'Account {user.email} and its scores were permanently deleted.')
                return redirect(url_for('admin'))

            if action == 'mark_draw_paid':
                draw = db.session.get(WeeklyDraw, request.form.get('draw_id', type=int))
                if draw is None:
                    flash('That weekly draw no longer exists.')
                elif not draw.winner_email:
                    flash('There is no winner to mark as paid for that draw.')
                else:
                    result = db.session.execute(
                        update(WeeklyDrawPayout)
                        .where(
                            WeeklyDrawPayout.draw_id == draw.id,
                            WeeklyDrawPayout.paid_at.is_(None),
                        )
                        .values(
                            paid_at=datetime.now(timezone.utc),
                            paid_by_email=current_user.email,
                        )
                    )
                    if result.rowcount:
                        db.session.commit()
                        flash(f'{draw.winner_name} is marked as paid.')
                    else:
                        db.session.rollback()
                        flash('That draw winner is already marked as paid.')
                return redirect(url_for('admin'))

            abort(400)

        users = User.query.order_by(User.name, User.email).all()
        user_summaries = [
            {
                'user': user,
                'sessions': sum(entry.score_count for entry in user.entries),
                'made': sum(entry.total for entry in user.entries),
                'history': sorted(
                    user.entries,
                    key=lambda entry: entry.week_key,
                    reverse=True,
                )[:1],
            }
            for user in users
        ]
        challenges = Challenge.query.order_by(Challenge.title).all()
        assignments = WeeklyChallenge.query.order_by(WeeklyChallenge.week_key.desc()).all()
        weekly_draws = WeeklyDraw.query.order_by(WeeklyDraw.week_key.desc()).limit(12).all()
        payouts_by_draw_id = {
            payout.draw_id: payout
            for payout in WeeklyDrawPayout.query.filter(
                WeeklyDrawPayout.draw_id.in_([draw.id for draw in weekly_draws])
            ).all()
        } if weekly_draws else {}
        return render_template(
            'pages/admin.html',
            users=user_summaries,
            challenges=challenges,
            assignments=assignments,
            weekly_draws=weekly_draws,
            payouts_by_draw_id=payouts_by_draw_id,
            current_week_key=current_week()[0],
        )

    @app.get('/auth/google')
    def google_login():
        if not app.config.get('GOOGLE_CLIENT_ID') or not app.config.get('GOOGLE_CLIENT_SECRET'):
            flash('Google sign-in needs GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET configured.')
            return redirect(url_for('home'))
        session['remember_login'] = request.args.get('remember') == '1'
        redirect_uri = url_for('google_callback', _external=True)
        return oauth.google.authorize_redirect(redirect_uri)

    @app.get('/auth/callback')
    def google_callback():
        token = oauth.google.authorize_access_token()
        profile = token.get('userinfo') or oauth.google.parse_id_token(token)
        if not profile or not profile.get('sub') or not profile.get('email'):
            abort(400, 'Google did not provide a verified account profile.')

        user = User.query.filter_by(google_id=profile['sub']).first()
        if user is None:
            user = User(
                google_id=profile['sub'],
                email=profile['email'],
                name=profile.get('name') or profile['email'].split('@')[0],
            )
            db.session.add(user)
        else:
            user.email = profile['email']
            user.name = profile.get('name') or user.name
        db.session.commit()
        login_user(user, remember=session.pop('remember_login', False))
        return redirect(url_for('home'))

    @app.post('/scores')
    @login_required
    def submit_score():
        form = ScoreForm()
        if not form.validate_on_submit():
            flash('Enter the number of made putts, from 0 to 20.')
            return redirect(url_for('home'))

        sequence_value = request.form.get('putt_sequence', '').strip()
        sequence = None
        if sequence_value:
            try:
                sequence = json.loads(sequence_value)
            except json.JSONDecodeError:
                flash('The make/miss sequence is invalid. Please record the set again.')
                return redirect(url_for('home'))
            if (
                not isinstance(sequence, list)
                or len(sequence) != 20
                or any(type(result) is not bool for result in sequence)
                or sum(sequence) != form.score.data
            ):
                flash('The make/miss sequence must contain 20 results matching your score.')
                return redirect(url_for('home'))

        week_key, week_start = current_week()
        entry = WeeklyEntry.query.filter_by(
            week_key=week_key, user_id=current_user.id
        ).first()
        if entry is None:
            entry = WeeklyEntry(
                user_id=current_user.id,
                week_key=week_key,
                week_start=week_start,
            )
            db.session.add(entry)

        next_slot = next(
            (index for index, score in enumerate(entry.scores, start=1) if score is None),
            None,
        )
        if next_slot is None:
            flash('Your five scores for this week are already submitted.')
            return redirect(url_for('home'))

        setattr(entry, f'score_{next_slot}', form.score.data)
        if sequence is not None:
            db.session.add(PuttSequence(
                weekly_entry=entry,
                set_number=next_slot,
                results=json.dumps(sequence),
            ))
        db.session.commit()
        flash(f'Session {next_slot} of 5 saved.')
        return redirect(url_for('home'))

    @app.get('/history')
    @login_required
    def player_history():
        entries_query = WeeklyEntry.query.filter_by(user_id=current_user.id).order_by(
            WeeklyEntry.week_start.desc()
        )
        total_weeks = entries_query.count()
        requested_limit = request.args.get('limit', 10, type=int) or 10
        history_limit = min(max(requested_limit, 10), total_weeks or 10)
        entries = entries_query.limit(history_limit).all()
        summary = db.session.query(
            func.count(WeeklyEntry.score_1)
            + func.count(WeeklyEntry.score_2)
            + func.count(WeeklyEntry.score_3)
            + func.count(WeeklyEntry.score_4)
            + func.count(WeeklyEntry.score_5),
            func.coalesce(func.sum(WeeklyEntry.score_1), 0)
            + func.coalesce(func.sum(WeeklyEntry.score_2), 0)
            + func.coalesce(func.sum(WeeklyEntry.score_3), 0)
            + func.coalesce(func.sum(WeeklyEntry.score_4), 0)
            + func.coalesce(func.sum(WeeklyEntry.score_5), 0),
        ).filter(WeeklyEntry.user_id == current_user.id).one()
        tracked_set_count = PuttSequence.query.join(WeeklyEntry).filter(
            WeeklyEntry.user_id == current_user.id
        ).count()
        week_keys = {entry.week_key for entry in entries}
        challenge_titles = {}
        if week_keys:
            challenge_titles = dict(
                db.session.query(WeeklyChallenge.week_key, Challenge.title)
                .join(Challenge)
                .filter(WeeklyChallenge.week_key.in_(week_keys))
                .all()
            )
        sequences = {}
        entry_ids = [entry.id for entry in entries]
        if entry_ids:
            for saved_sequence in PuttSequence.query.filter(
                PuttSequence.weekly_entry_id.in_(entry_ids)
            ).all():
                sequences[(saved_sequence.weekly_entry_id, saved_sequence.set_number)] = (
                    analyze_putt_sequence(json.loads(saved_sequence.results))
                )

        history = []
        for entry in entries:
            sets = []
            for set_number, score in enumerate(entry.scores, start=1):
                if score is not None:
                    sets.append({
                        'number': set_number,
                        'score': score,
                        'analysis': sequences.get((entry.id, set_number)),
                    })
            history.append({
                'week_key': entry.week_key,
                'week_start': entry.week_start,
                'challenge_title': challenge_titles.get(entry.week_key),
                'sets': sets,
                'total': entry.total,
            })
        return render_template(
            'pages/history.html',
            history=history,
            total_weeks=total_weeks,
            history_limit=history_limit,
            total_sessions=summary[0],
            total_made=summary[1],
            tracked_set_count=tracked_set_count,
        )

    @app.post('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('home'))

    return app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
