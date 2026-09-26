#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#

from datetime import datetime, timedelta, timezone
import os

from authlib.integrations.flask_client import OAuth
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf import CSRFProtect, FlaskForm
from wtforms import IntegerField
from wtforms.validators import InputRequired, NumberRange

from models import User, WeeklyEntry, db

login_manager = LoginManager()
login_manager.login_view = 'home'
login_manager.login_message = 'Sign in with Google to submit a score.'
oauth = OAuth()


class ScoreForm(FlaskForm):
    score = IntegerField(
        'Made putts',
        validators=[InputRequired(), NumberRange(min=0, max=20)],
    )


def current_week(now=None):
    now = now or datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).date()
    iso_year, iso_week, _ = monday.isocalendar()
    return f'{iso_year}-W{iso_week:02d}', monday


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

    @app.get('/')
    def home():
        week_key, week_start = current_week()
        entries = WeeklyEntry.query.filter_by(week_key=week_key).all()
        standings = sorted(
            entries,
            key=lambda entry: (-entry.total, -entry.score_count, entry.user.name.casefold()),
        )
        player_entry = None
        if current_user.is_authenticated:
            player_entry = WeeklyEntry.query.filter_by(
                week_key=week_key, user_id=current_user.id
            ).first()
        form = ScoreForm()
        return render_template(
            'pages/placeholder.home.html',
            week_key=week_key,
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            standings=standings,
            participants=len(entries),
            sessions_total=sum(entry.score_count for entry in entries),
            player_entry=player_entry,
            form=form,
            weekly_task=app.config.get('WEEKLY_TASK', '20 putts from 20 feet'),
            google_ready=bool(
                app.config.get('GOOGLE_CLIENT_ID')
                and app.config.get('GOOGLE_CLIENT_SECRET')
            ),
        )

    @app.get('/auth/google')
    def google_login():
        if not app.config.get('GOOGLE_CLIENT_ID') or not app.config.get('GOOGLE_CLIENT_SECRET'):
            flash('Google sign-in needs GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET configured.')
            return redirect(url_for('home'))
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
        login_user(user)
        return redirect(url_for('home'))

    @app.post('/scores')
    @login_required
    def submit_score():
        form = ScoreForm()
        if not form.validate_on_submit():
            flash('Enter the number of made putts, from 0 to 20.')
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
        db.session.commit()
        flash(f'Session {next_slot} of 5 saved.')
        return redirect(url_for('home'))

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
