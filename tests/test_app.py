import os
import tempfile
import unittest
from datetime import timedelta
from unittest.mock import patch

from app import create_app, current_week, week_key_for
from config import SQLALCHEMY_ENGINE_OPTIONS, database_uri_from_environment
from models import Challenge, User, WeeklyChallenge, WeeklyDraw, WeeklyEntry, db


class DatabaseConfigurationTests(unittest.TestCase):
    def test_database_pool_checks_connections_before_use(self):
        self.assertTrue(SQLALCHEMY_ENGINE_OPTIONS['pool_pre_ping'])

    def test_defaults_to_sqlite_without_mysql_settings(self):
        with patch.dict(os.environ, {}, clear=True):
            database_uri = database_uri_from_environment()

        self.assertTrue(database_uri.startswith('sqlite:///'))

    def test_builds_mysql_url_without_corrupting_password(self):
        settings = {
            'PUTTING_LEAGUE_DB_HOST': 'mysql.example.test',
            'PUTTING_LEAGUE_DB_NAME': 'aaronlael$puttingleague',
            'PUTTING_LEAGUE_DB_USER': 'league-user',
            'PUTTING_LEAGUE_DB_PASSWORD': 'p@ss/word',
        }
        with patch.dict(os.environ, settings, clear=True):
            database_uri = database_uri_from_environment()

        self.assertEqual(database_uri.drivername, 'mysql+mysqlconnector')
        self.assertEqual(database_uri.host, 'mysql.example.test')
        self.assertEqual(database_uri.database, 'aaronlael$puttingleague')
        self.assertEqual(database_uri.password, 'p@ss/word')

    def test_rejects_partial_mysql_settings(self):
        with patch.dict(os.environ, {'PUTTING_LEAGUE_DB_HOST': 'mysql.example.test'}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'PUTTING_LEAGUE_DB_NAME'):
                database_uri_from_environment()


class WeeklyLeagueTests(unittest.TestCase):
    def setUp(self):
        self.database_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.database_file.close()
        self.app = create_app({
            'TESTING': True,
            'WTF_CSRF_ENABLED': False,
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{self.database_file.name}',
            'SECRET_KEY': 'test-secret',
            'ADMIN_EMAIL': 'AARON.J.LAEL@GMAIL.COM',
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            self.alex = User(google_id='google-alex', email='alex@example.com', name='Alex')
            self.blair = User(google_id='google-blair', email='blair@example.com', name='Blair')
            self.admin_user = User(
                google_id='google-admin',
                email='aaron.j.lael@gmail.com',
                name='Aaron',
            )
            db.session.add_all([self.alex, self.blair, self.admin_user])
            db.session.commit()
            self.alex_id = self.alex.id
            self.blair_id = self.blair.id
            self.admin_id = self.admin_user.id

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

    def test_admin_page_is_restricted_to_allowlisted_email(self):
        self.sign_in(self.blair_id)
        self.assertEqual(self.client.get('/admin').status_code, 403)
        self.assertEqual(self.client.post('/admin', data={'action': 'add_challenge'}).status_code, 403)

        self.sign_in(self.admin_id)
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Administration', response.data)

    def test_admin_can_add_challenge_and_assign_it_to_a_week(self):
        self.sign_in(self.admin_id)
        response = self.client.post('/admin', data={
            'action': 'add_challenge',
            'title': 'Clockwork Circle',
            'description': 'Make putts from three marked distances.',
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            challenge = Challenge.query.filter_by(title='Clockwork Circle').one()
            challenge_id = challenge.id

        week_key, _ = current_week()
        response = self.client.post('/admin', data={
            'action': 'schedule_week',
            'week_key': week_key,
            'challenge_id': challenge_id,
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Clockwork Circle', self.client.get('/').data)
        self.assertIn(b'Make putts from three marked distances.', self.client.get('/').data)

        with self.app.app_context():
            assignment = WeeklyChallenge.query.filter_by(week_key=week_key).one()
            self.assertEqual(assignment.challenge.title, 'Clockwork Circle')

    def test_admin_can_delete_player_and_all_scores_but_not_self(self):
        with self.app.app_context():
            key, start = current_week()
            db.session.add(WeeklyEntry(
                user_id=self.blair_id,
                week_key=key,
                week_start=start,
                score_1=12,
            ))
            db.session.commit()

        self.sign_in(self.admin_id)
        review_page = self.client.get('/admin')
        self.assertIn(b'12', review_page.data)
        self.assertIn(current_week()[0].encode(), review_page.data)
        response = self.client.post('/admin', data={
            'action': 'delete_user',
            'user_id': self.admin_id,
        }, follow_redirects=True)
        self.assertIn(b'cannot delete your own admin account', response.data)

        response = self.client.post('/admin', data={
            'action': 'delete_user',
            'user_id': self.blair_id,
        }, follow_redirects=True)
        self.assertIn(b'permanently deleted', response.data)
        with self.app.app_context():
            self.assertIsNone(db.session.get(User, self.blair_id))
            self.assertEqual(WeeklyEntry.query.filter_by(user_id=self.blair_id).count(), 0)

    def test_previous_week_draw_is_once_only_and_only_full_rounds_are_eligible(self):
        _, this_monday = current_week()
        previous_monday = this_monday - timedelta(days=7)
        previous_key = week_key_for(previous_monday)
        with self.app.app_context():
            alex_entry = WeeklyEntry(
                user_id=self.alex_id,
                week_key=previous_key,
                week_start=previous_monday,
                score_1=15,
                score_2=16,
                score_3=17,
                score_4=18,
                score_5=19,
            )
            admin_entry = WeeklyEntry(
                user_id=self.admin_id,
                week_key=previous_key,
                week_start=previous_monday,
                score_1=10,
                score_2=10,
                score_3=10,
                score_4=10,
                score_5=10,
            )
            partial_entry = WeeklyEntry(
                user_id=self.blair_id,
                week_key=previous_key,
                week_start=previous_monday,
                score_1=20,
                score_2=20,
                score_3=20,
                score_4=20,
            )
            db.session.add_all([alex_entry, admin_entry, partial_entry])
            db.session.commit()

        def choose_alex(eligible_entries):
            self.assertEqual(
                {entry.user.email for entry in eligible_entries},
                {'alex@example.com', 'aaron.j.lael@gmail.com'},
            )
            return next(entry for entry in eligible_entries if entry.user_id == self.alex_id)

        with patch('app.secrets.choice', side_effect=choose_alex) as random_choice:
            public_page = self.client.get('/')
            self.assertEqual(public_page.status_code, 200)
            self.client.get('/')
            self.assertEqual(random_choice.call_count, 1)

        self.assertIn(b'LAST WEEK', public_page.data)
        self.assertIn(b'Alex', public_page.data)
        self.assertNotIn(b'alex@example.com', public_page.data)
        with self.app.app_context():
            draw = WeeklyDraw.query.filter_by(week_key=previous_key).one()
            self.assertEqual(draw.winner_name, 'Alex')
            self.assertEqual(draw.winner_email, 'alex@example.com')
            self.assertEqual(draw.winner_total, 85)
            self.assertEqual(draw.eligible_count, 2)

        self.sign_in(self.admin_id)
        admin_page = self.client.get('/admin')
        self.assertIn(b'alex@example.com', admin_page.data)

    def test_week_with_no_full_round_submissions_records_no_winner(self):
        _, this_monday = current_week()
        previous_monday = this_monday - timedelta(days=7)
        previous_key = week_key_for(previous_monday)
        with self.app.app_context():
            db.session.add(WeeklyEntry(
                user_id=self.blair_id,
                week_key=previous_key,
                week_start=previous_monday,
                score_1=20,
                score_2=20,
            ))
            db.session.commit()

        with patch('app.secrets.choice') as random_choice:
            response = self.client.get('/')
            random_choice.assert_not_called()
        self.assertIn(b'No eligible winner', response.data)
        with self.app.app_context():
            draw = WeeklyDraw.query.filter_by(week_key=previous_key).one()
            self.assertIsNone(draw.winner_name)
            self.assertEqual(draw.eligible_count, 0)

    def test_empty_previous_week_still_gets_a_no_winner_record(self):
        _, this_monday = current_week()
        previous_key = week_key_for(this_monday - timedelta(days=7))

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'No eligible winner', response.data)
        with self.app.app_context():
            draw = WeeklyDraw.query.filter_by(week_key=previous_key).one()
            self.assertIsNone(draw.winner_email)
            self.assertEqual(draw.eligible_count, 0)


if __name__ == '__main__':
    unittest.main()