import os
import logging
import asyncio
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from datetime import datetime

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Config
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
ADMIN_USER_IDS = [int(x) for x in os.environ.get('ADMIN_USER_IDS', '').split(',') if x]
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
BASE_URL = os.environ.get('BASE_URL', os.environ.get('VERCEL_URL', ''))

if BASE_URL and not BASE_URL.startswith('http'):
    BASE_URL = f'https://{BASE_URL}'

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admin_suffix = ' [ADMIN]' if is_admin(user.id) else ''
    
    keyboard = [
        [InlineKeyboardButton('Ver Planes', callback_data='view_plans')],
        [InlineKeyboardButton('Mi Cuenta', callback_data='my_account'),
         InlineKeyboardButton('Soporte', url='https://t.me/BarbosaAgencyProBot')]
    ]
    
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton('Panel Admin', callback_data='admin')])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        'Hola ' + user.first_name + admin_suffix + '!\n\n'
        '*BARBOSA AGENCY PRO*\n'
        'Su plataforma de automatizacion.\n\n'
        'Que desea hacer?'
    )
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == 'view_plans':
        await show_plans(query)
    elif data == 'my_account':
        await show_account(query)
    elif data == 'admin':
        await show_admin(query)
    elif data.startswith('buy_'):
        tier = data.replace('buy_', '')
        await process_payment(query, tier)
    else:
        await query.edit_message_text('Opcion no disponible aun.')

async def show_plans(query):
    keyboard = [
        [InlineKeyboardButton('BASIC $9/mes', callback_data='buy_basic')],
        [InlineKeyboardButton('PRO $29/mes', callback_data='buy_pro')],
        [InlineKeyboardButton('ENTERPRISE $99/mes', callback_data='buy_enterprise')],
        [InlineKeyboardButton('Volver', callback_data='back_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = '*Planes Disponibles*\n\nElige el plan que mejor se adapte a tu negocio:'
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_account(query):
    text = '*Mi Cuenta*\n\nGestion de cuenta en desarrollo.'
    keyboard = [[InlineKeyboardButton('Volver', callback_data='back_main')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_admin(query):
    text = '*Panel Admin*\n\nBienvenido al panel de administracion.'
    keyboard = [[InlineKeyboardButton('Volver', callback_data='back_main')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def process_payment(query, tier):
    prices = {
        'basic': ('Plan BASIC', '$9/mes'),
        'pro': ('Plan PRO', '$29/mes'),
        'enterprise': ('Plan ENTERPRISE', '$99/mes')
    }
    plan_name, price = prices.get(tier, ('Plan Desconocido', 'N/A'))
    text = (
        f'*{plan_name} - {price}*\n\n'
        'Para procesar el pago, contacta al administrador:\n'
        '@BarbosaAgencyProBot\n\n'
        'Stripe en configuracion.'
    )
    keyboard = [[InlineKeyboardButton('Volver', callback_data='view_plans')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# Telegram app global
ptb_app = None

async def get_ptb_app():
    global ptb_app
    if ptb_app is None:
        ptb_app = (
            Application.builder()
            .token(TELEGRAM_TOKEN)
            .build()
        )
        ptb_app.add_handler(CommandHandler('start', start))
        ptb_app.add_handler(CallbackQueryHandler(handle_callback))
        await ptb_app.initialize()
    return ptb_app

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_process_update())
        loop.close()
        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f'Webhook error: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500

async def _process_update():
    data = request.get_json(force=True)
    application = await get_ptb_app()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)

@app.route('/', methods=['GET'])
def index():
    return jsonify({'status': 'ok', 'bot': 'Barbosa Agency Pro Bot', 'version': '1.0'})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
