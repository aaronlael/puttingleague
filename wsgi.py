import os
import sys

from wsgi_adapter import create_application

putting_league_home = os.path.dirname(os.path.abspath(__file__))
if putting_league_home in sys.path:
	sys.path.remove(putting_league_home)
sys.path.insert(0, putting_league_home)

from app import app as putting_league_app

bcss_home = os.environ.get('BCSS_HOME')
if not bcss_home:
	raise RuntimeError('Set BCSS_HOME to the existing BCSS app directory.')
if bcss_home in sys.path:
	sys.path.remove(bcss_home)
sys.path.insert(0, bcss_home)

from flask_app import app as bcss_app

application = create_application(bcss_app, putting_league_app)