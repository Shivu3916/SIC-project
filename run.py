"""
Entry point for the Viva Simulator Flask application.
Run: python run.py
"""
from app_factory import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
