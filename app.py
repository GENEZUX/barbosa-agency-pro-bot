# Vercel entry point - imports Flask app from bot/main.py
from bot.main import app

# This exposes the Flask 'app' object for Vercel's WSGI handler
# All routes are defined in bot/main.py including /webhook/telegram

if __name__ == '__main__':
    app.run(debug=False)
