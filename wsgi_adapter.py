from werkzeug.middleware.dispatcher import DispatcherMiddleware


def create_application(bcss_app, putting_league_app):
    putting_league_app.config['SESSION_COOKIE_NAME'] = 'putting_league_session'
    putting_league_app.config['SESSION_COOKIE_PATH'] = '/puttingleague'
    putting_league_app.config['SESSION_COOKIE_SECURE'] = True
    putting_league_app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    return DispatcherMiddleware(
        bcss_app,
        {'/puttingleague': putting_league_app},
    )