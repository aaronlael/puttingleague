import os
import tempfile
import unittest

from app import create_app, current_week
from models import User, WeeklyEntry, db


class WeeklyLeagueTests(unittest.TestCase):
    def setUp(self):
        self.database_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.database_file.close()
        self.app = create_app({
            'TESTING': True,
            'WTF_CSRF_ENABLED': False,
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{self.database_file.name}',
            'SECRET_KEY': 'test-secret',
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            self.alex = User(google_id='google-alex', email='alex@example.com', name='Alex')
            self.blair = User(google_id='google-blair', email='blair@example.com', name='Blair')
            db.session.add_all([self.alex, self.blair])
            db.session.commit()
            self.alex_id = self.alex.id
            self.blair_id = self.blair.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.unlink(self.database_file.name)

    def sign_in(self, user_id):
        with self.client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True

    def test_session_cap_and_highest_partial_total_ranks_first(self):
        self.sign_in(self.alex_id)
        for score in (4, 3, 5, 2, 4):
            response = self.client.post('/scores', data={'score': score}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
        response = self.client.post('/scores', data={'score': 1}, follow_redirects=True)
        self.assertIn(b'already submitted', response.data)

        self.sign_in(self.blair_id)
        for score in (20, 20):
            self.client.post('/scores', data={'score': score})
        page = self.client.get('/')
        blair_row = page.data.index(b'class="player-name">Blair')
        alex_row = page.data.index(b'class="player-name">Alex')
        self.assertLess(blair_row, alex_row)
        self.assertIn(b'2/5', page.data)
        self.assertIn(b'>40</strong>', page.data)

        for score in (0, 0, 0):
            self.client.post('/scores', data={'score': score})
        self.client.post('/logout')
        page = self.client.get('/')
        blair_row = page.data.index(b'class="player-name">Blair')
        alex_row = page.data.index(b'class="player-name">Alex')
        self.assertLess(blair_row, alex_row)
        self.assertIn(b'5/5', page.data)
        self.assertIn(b'>40</strong>', page.data)

    def test_session_made_putts_must_be_between_zero_and_twenty(self):
        self.sign_in(self.alex_id)
        for score in (-1, 21):
            response = self.client.post('/scores', data={'score': score}, follow_redirects=True)
            self.assertIn(b'number of made putts, from 0 to 20', response.data)
        response = self.client.post('/scores', data={'score': 0}, follow_redirects=True)
        self.assertIn(b'Session 1 of 5 saved.', response.data)

    def test_week_key_is_iso_monday_based(self):
        key, start = current_week()
        self.assertEqual(start.weekday(), 0)
        self.assertEqual(key, f'{start.isocalendar().year}-W{start.isocalendar().week:02d}')

    def test_score_submission_requires_sign_in(self):
        response = self.client.post('/scores', data={'score': 4})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/?next=%2Fscores', response.headers['Location'])


if __name__ == '__main__':
    unittest.main()