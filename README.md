[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Putting League

A weekly putting competition with Google sign-in, up to five sessions per player, and a Monday-to-Sunday UTC leaderboard. Each session records made putts for the weekly task (20 putts per session by default, configurable with `WEEKLY_TASK`). Players are ranked by total made putts so far, with completed session count shown beside each total. A new ISO week starts a fresh board while previous weeks remain stored.

### Run locally

1. Create and activate a Python virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Create a Google OAuth 2.0 Web application client. Add `http://localhost:5000/auth/callback` as an authorized redirect URI.
4. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and a private `SECRET_KEY` environment variable.
5. Start the app with `python app.py` and visit `http://localhost:5000`.

The SQLite database is created as `database.db` on first run. Back it up regularly, use HTTPS for public deployment, and consider an external database if usage or recovery requirements grow. Set `ADMIN_EMAIL` in the deployment environment to `aaron.j.lael@gmail.com` to grant that Google account access to `/admin` (this is the default). The admin page lets you create challenges, assign them to ISO weeks, review weekly score histories, and permanently remove player accounts and their scores. New challenge, schedule, and weekly-draw tables are created automatically; existing database tables are unchanged.

When the first request arrives after a week ends, the app records one random winner from players who submitted all five rounds. The homepage keeps last week's top five and winner in a collapsed history panel; the winner's email is shown only in the admin draw history. This is request-triggered rather than a timed email notification, so the draw happens on the first app request after the UTC week boundary.

### Merge Into Existing BCSS on PythonAnywhere

Keep the deployed BCSS files in `/home/yourusername/mysite` as they are, including its lowercase `static/` and `templates/` directories. Put this repository beside it, for example in `/home/yourusername/puttingleague`. The existing PythonAnywhere web app and domain stay in use: BCSS remains at `/`, and Putting League is mounted at `/puttingleague`.

1. Back up the current BCSS WSGI file and code. In a Bash console, run `cd /home/yourusername` followed by `git clone <repository-url> puttingleague`. This checks out the Putting League repository into `/home/yourusername/puttingleague`; leave `mysite` and the separate BCSS repository untouched. Set `BCSS_HOME` to `/home/yourusername/mysite` so the adapter loads BCSS from its existing directory.
2. This web app uses Python 3.10 with no virtualenv. After pulling updates, install requirements into the same user environment with `cd /home/yourusername/puttingleague` followed by `python3.10 -m pip install --user -r requirements.txt`. These packages are shared with BCSS, so review package changes before upgrading anything already in use.
3. In the WSGI configuration file linked from the existing Web tab, keep BCSS's current `.env` and load it, then load Putting League's `.env` before importing either app. Generate `SECRET_KEY` privately with `python -c "import secrets; print(secrets.token_hex(32))"`; keep Putting League's `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `ADMIN_EMAIL` in `/home/yourusername/puttingleague/.env`, which is ignored by Git. Adjust the paths in this adapter:

    ```python
    import os
    import sys
    from dotenv import load_dotenv

    bcss_home = '/home/yourusername/mysite'
    putting_league_home = '/home/yourusername/puttingleague'
    if putting_league_home not in sys.path:
        sys.path.insert(0, putting_league_home)

    load_dotenv(os.path.join(bcss_home, '.env'))
    load_dotenv(os.path.join(putting_league_home, '.env'))
    os.environ['BCSS_HOME'] = bcss_home

    from wsgi import application
    ```

    Keep BCSS's existing Basic Auth and MySQL values in its `.env`. The repository's `wsgi.py` requires `BCSS_HOME` and imports `flask_app.py` from that directory.
    Add the following settings to `/home/yourusername/puttingleague/.env`, using the MySQL host and username from PythonAnywhere/BCSS, and the full name of the new Putting League database. The password can be the same as BCSS's; the separate variable names prevent the app from selecting BCSS's database by mistake.

    ```ini
    PUTTING_LEAGUE_DB_HOST=your-mysql-host
    PUTTING_LEAGUE_DB_NAME=yourusername$puttingleague
    PUTTING_LEAGUE_DB_USER=your-mysql-user
    PUTTING_LEAGUE_DB_PASSWORD=your-mysql-password
    ```

    The app creates its tables in this database when it starts. Back up the SQLite `database.db`, then preview the migration from the project directory with `python3.10 migrate_sqlite_to_mysql.py`. If the counts are correct and the MySQL app tables are empty, pause score submissions and run `python3.10 migrate_sqlite_to_mysql.py --apply`. The script preserves IDs, copies in foreign-key order, and never modifies the SQLite source. It refuses to copy into non-empty MySQL app tables.
4. Leave the existing `/static/` mapping pointed at `/home/yourusername/mysite/static/`. Add `/puttingleague/static/` mapped to `/home/yourusername/puttingleague/static/`.
5. In Google Cloud Console, add `https://yourusername.pythonanywhere.com/puttingleague/auth/callback` as an authorized redirect URI. Keep BCSS's domain and other OAuth settings unchanged.
6. After checking the environment variables and WSGI paths, reload the existing web app. Confirm BCSS still opens at `/` and Putting League opens at `/puttingleague`; check the PythonAnywhere error log if startup fails.

Putting League creates `database.db` inside `/home/yourusername/puttingleague`; back it up separately. BCSS continues using its existing MySQL database and scheduled-task setup.

## Acknowledgments

Thanks to [Real Python](https://github.com/realpython/flask-boilerplate) for the original Flask boilerplate this project started from.

