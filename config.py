import os

from sqlalchemy.engine import URL

# Grabs the folder where the script runs.
basedir = os.path.abspath(os.path.dirname(__file__))

# Enable debug mode.
DEBUG = False

# Secret key for session management. You can generate random strings here:
# https://randomkeygen.com/
SECRET_KEY = os.environ.get('SECRET_KEY')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'aaron.j.lael@gmail.com')
WEEKLY_TASK = os.environ.get('WEEKLY_TASK', '20 putts from 20 feet')

def database_uri_from_environment():
	mysql_settings = {
		'host': os.environ.get('PUTTING_LEAGUE_DB_HOST'),
		'name': os.environ.get('PUTTING_LEAGUE_DB_NAME'),
		'user': os.environ.get('PUTTING_LEAGUE_DB_USER'),
		'password': os.environ.get('PUTTING_LEAGUE_DB_PASSWORD'),
	}
	if not any(mysql_settings.values()):
		return 'sqlite:///' + os.path.join(basedir, 'database.db')

	missing_settings = [name for name, value in mysql_settings.items() if not value]
	if missing_settings:
		missing_names = ', '.join(f'PUTTING_LEAGUE_DB_{name.upper()}' for name in missing_settings)
		raise RuntimeError(f'Missing database environment settings: {missing_names}')

	return URL.create(
		'mysql+mysqlconnector',
		username=mysql_settings['user'],
		password=mysql_settings['password'],
		host=mysql_settings['host'],
		database=mysql_settings['name'],
	)


SQLALCHEMY_DATABASE_URI = database_uri_from_environment()
