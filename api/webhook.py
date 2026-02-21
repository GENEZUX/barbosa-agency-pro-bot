import json
import os
import sys
import asyncio
from http.server import BaseHTTPRequestHandler

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.ext import Application
from bot.main import setup_handlers, TELEGRAM_TOKEN

_app = None

async def get_application():
    global _app
    if _app is None:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        setup_handlers(application)
        await application.initialize()
        _app = application
    return _app


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {'status': 'ok', 'bot': 'BarbosaAgencyProBot', 'version': '2.0.0'}
        self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            update_data = json.loads(body)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def process():
                app = await get_application()
                update = Update.de_json(update_data, app.bot)
                await app.process_update(update)
            
            try:
                loop.run_until_complete(process())
            finally:
                loop.close()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': True}).encode())
            
        except Exception as e:
            print(f'Error processing update: {e}')
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def log_message(self, format, *args):
        pass
