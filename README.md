[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Putting League

A weekly putting competition with Google sign-in, up to five sessions per player, and a Monday-to-Sunday UTC leaderboard. Each session records made putts for the weekly task (20 putts per session by default, configurable with `WEEKLY_TASK`). Players are ranked by total made putts so far, with completed session count shown beside each total. A new ISO week starts a fresh board while previous weeks remain stored.

### Run locally

1. Create and activate a Python virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Create a Google OAuth 2.0 Web application client. Add `http://localhost:5000/auth/callback` as an authorized redirect URI.
4. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and a private `SECRET_KEY` environment variable.
5. Start the app with `python app.py` and visit `http://localhost:5000`.

The SQLite database is created as `database.db` on first run. Configure a durable database and HTTPS before deploying publicly. Set `ADMIN_EMAIL` in the deployment environment to `aaron.j.lael@gmail.com` to grant that Google account access to `/admin` (this is the default). The admin page lets you create challenges, assign them to ISO weeks, review weekly score histories, and permanently remove player accounts and their scores. New challenge, schedule, and weekly-draw tables are created automatically; existing database tables are unchanged.

When the first request arrives after a week ends, the app records one random winner from players who submitted all five rounds. The homepage keeps last week's top five and winner in a collapsed history panel; the winner's email is shown only in the admin draw history. This is request-triggered rather than a timed email notification, so the draw happens on the first app request after the UTC week boundary.

## Acknowledgments

Thanks to [Real Python](https://github.com/realpython/flask-boilerplate) for the original Flask boilerplate this project started from.

