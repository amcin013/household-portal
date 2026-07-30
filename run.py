"""Development server:  python3 run.py

Listens on every interface so you can open it from a phone on the same network.
Use gunicorn (see deploy/) for the real thing.
"""
from portal import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
