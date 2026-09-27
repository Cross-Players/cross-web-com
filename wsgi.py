"""WSGI entry point.

    flask --app wsgi --debug run             # development
    gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app   # production
"""

from app import create_app

app = create_app()
