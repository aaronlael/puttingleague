import os

# Grabs the folder where the script runs.
basedir = os.path.abspath(os.path.dirname(__file__))

# Enable debug mode.
DEBUG = False

# Secret key for session management. You can generate random strings here:
# https://randomkeygen.com/
SECRET_KEY = os.environ.get('SECRET_KEY')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
WEEKLY_TASK = os.environ.get('WEEKLY_TASK', '20 putts from 20 feet')

# Connect to the database
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'database.db')
