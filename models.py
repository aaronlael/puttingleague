from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    entries = db.relationship('WeeklyEntry', back_populates='user')


class Challenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False, unique=True)
    description = db.Column(db.String(500), nullable=False, default='')
    weeks = db.relationship('WeeklyChallenge', back_populates='challenge')


class WeeklyChallenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_key = db.Column(db.String(8), nullable=False, unique=True, index=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenge.id'), nullable=False)
    challenge = db.relationship('Challenge', back_populates='weeks')


class WeeklyDraw(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_key = db.Column(db.String(8), nullable=False, unique=True, index=True)
    winner_name = db.Column(db.String(120))
    winner_email = db.Column(db.String(255))
    winner_total = db.Column(db.Integer)
    eligible_count = db.Column(db.Integer, nullable=False, default=0)
    drawn_at = db.Column(db.DateTime(timezone=True), nullable=False)


class WeeklyEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    week_key = db.Column(db.String(8), nullable=False, index=True)
    week_start = db.Column(db.Date, nullable=False)
    score_1 = db.Column(db.Integer)
    score_2 = db.Column(db.Integer)
    score_3 = db.Column(db.Integer)
    score_4 = db.Column(db.Integer)
    score_5 = db.Column(db.Integer)
    user = db.relationship('User', back_populates='entries')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'week_key', name='one_entry_per_player_week'),
    )

    @property
    def scores(self):
        return [
            self.score_1,
            self.score_2,
            self.score_3,
            self.score_4,
            self.score_5,
        ]

    @property
    def completed_scores(self):
        return [score for score in self.scores if score is not None]

    @property
    def score_count(self):
        return len(self.completed_scores)

    @property
    def total(self):
        return sum(self.completed_scores)
