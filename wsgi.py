"""Entry point for gunicorn:  gunicorn -w 3 -b 127.0.0.1:8000 wsgi:app"""
from portal import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
