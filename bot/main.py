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
        keyboard.append([InlineKeyboardButton('Panel Admin', callback_data='admin_panel')])
    
    text = f'Hola {user.first_name}{admin_suffix}!

*BARBOSA AGENCY PRO*
Tu asistente de automatización.

¿Qué deseas hacer?'
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def view_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = '*PLANES BARBOSA AGENCY*

*BASICO - $9/mes*
*PRO - $29/mes*
*ENTERPRISE - $99/mes*'
    keyboard = [
        [InlineKeyboardButton('Stripe - Basico $9', callback_data='pay_stripe_basic'),
         InlineKeyboardButton('Stripe - Pro $29', callback_data='pay_stripe_pro')],
        [InlineKeyboardButton('Stripe - Enterprise $99', callback_data='pay_stripe_enterprise')],
        [InlineKeyboardButton('Volver', callback_data='start')]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tier = query.data.replace('pay_stripe_', '')
    
    # Sync workaround for Vercel
    await query.answer('Procesando...', show_alert=False)
    
    if not STRIPE_SECRET_KEY:
        await query.edit_message_text('Stripe no configurado.', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Volver', callback_data='view_plans')]]))
        return

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        price_ids = {
            'basic': os.environ.get('STRIPE_PRICE_BASIC', 'price_placeholder'),
            'pro': os.environ.get('STRIPE_PRICE_PRO', 'price_placeholder'),
            'enterprise': os.environ.get('STRIPE_PRICE_ENTERPRISE', 'price_placeholder')
        }
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_ids.get(tier), 'quantity': 1}],
            mode='subscription',
            success_url=f'{BASE_URL}/payment/success',
            cancel_url=f'{BASE_URL}/payment/cancel',
        )
        
        await query.edit_message_text(f'Paga tu plan {tier.upper()} aquí:', 
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Pagar Ahora', url=session.url), InlineKeyboardButton('Volver', callback_data='view_plans')]]))
    except Exception as e:
        logger.error(f'Stripe error: {e}')
        await query.edit_message_text(f'Error: {str(e)[:50]}', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Volver', callback_data='view_plans')]]))

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    text = f'*MI CUENTA*

ID: `{user.id}`
Usuario: @{user.username}
Plan: *FREE*'
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Volver', callback_data='start')]]), parse_mode='Markdown')

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer('No autorizado', show_alert=True)
        return
    await query.answer()
    await query.edit_message_text('*PANEL ADMIN*
Status: Online
Deploy: Vercel', 
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Volver', callback_data='start')]]), parse_mode='Markdown')

def setup_handlers(application: Application):
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(start, pattern='^start$'))
    application.add_handler(CallbackQueryHandler(view_plans, pattern='^view_plans$'))
    application.add_handler(CallbackQueryHandler(my_account, pattern='^my_account$'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern='^pay_stripe_'))

@app.route('/')
def index():
    return jsonify({'status': 'active'})

@app.route('/webhook', methods=['POST'])
def webhook():
    async def process():
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        setup_handlers(application)
        await application.initialize()
        update = Update.de_json(request.get_json(force=True), application.bot)
        await application.process_update(update)
        await application.shutdown()
    
    asyncio.run(process())
    return 'OK', 200

if __name__ == '__main__':
    app.run()
