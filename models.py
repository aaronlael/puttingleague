from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    entries = db.relationship('WeeklyEntry', back_populates='user')


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
