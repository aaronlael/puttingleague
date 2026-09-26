import unittest

from flask import Flask
from werkzeug.test import Client
from werkzeug.wrappers import Response

from app import app as putting_league_app
from wsgi_adapter import create_application


class WSGIMountTests(unittest.TestCase):
    def setUp(self):
        bcss_app = Flask('bcss_test')

        @bcss_app.get('/')
        def bcss_home():
            return 'BCSS'

        application = create_application(bcss_app, putting_league_app)
        self.client = Client(application, Response)

    def test_bcss_remains_at_domain_root(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), 'BCSS')

    def test_putting_league_static_files_use_subpath(self):
        response = self.client.get('/puttingleague/static/css/league.css')
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIn('text/css', response.content_type)
        finally:
            response.close()


if __name__ == '__main__':
    unittest.main()