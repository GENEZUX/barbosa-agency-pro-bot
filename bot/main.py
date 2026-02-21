import os
import logging
import asyncio
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from datetime import datetime

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app for webhooks
app = Flask(__name__)

# Get config from env
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
ADMIN_USER_IDS = [int(x) for x in os.environ.get('ADMIN_USER_IDS', '').split(',') if x]
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
DATABASE_URL = os.environ.get('DATABASE_URL', '')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
MERCADOPAGO_ACCESS_TOKEN = os.environ.get('MERCADOPAGO_ACCESS_TOKEN', '')
BASE_URL = os.environ.get('BASE_URL', os.environ.get('VERCEL_URL', ''))
if BASE_URL and not BASE_URL.startswith('http'):
    BASE_URL = f'https://{BASE_URL}'

app.secret_key = SECRET_KEY

# Global application instance
_application = None

def get_application():
    global _application
    if _application is None:
        _application = Application.builder().token(TELEGRAM_TOKEN).build()
        setup_handlers(_application)
    return _application

# ===================== HELPERS =====================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS

# ===================== HANDLERS =====================
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
    welcome_text = (
        f'Hola {user.first_name or "Cliente"}{admin_suffix}!\n\n'
        '*BARBOSA AGENCY PRO BOT*\n'
        'Tu asistente de automatizacion profesional.\n\n'
        'Que deseas hacer hoy?'
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def view_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plans_text = (
        '*PLANES BARBOSA AGENCY*\n\n'
        '*BASICO - $9/mes*\n'
        '- 1 proyecto activo\n'
        '- Soporte email 48h\n'
        '- Reportes mensuales\n\n'
        '*PRO - $29/mes* (Popular)\n'
        '- 5 proyectos activos\n'
        '- Soporte prioritario 24h\n'
        '- Automatizaciones ilimitadas\n'
        '- API access\n\n'
        '*ENTERPRISE - $99/mes*\n'
        '- Proyectos ilimitados\n'
        '- Soporte 24/7 WhatsApp\n'
        '- Desarrollo custom\n'
        '- SLA garantizado\n'
    )
    keyboard = [
        [InlineKeyboardButton('Stripe - Basico $9', callback_data='pay_stripe_basic'),
         InlineKeyboardButton('Stripe - Pro $29', callback_data='pay_stripe_pro')],
        [InlineKeyboardButton('Stripe - Enterprise $99', callback_data='pay_stripe_enterprise')],
        [InlineKeyboardButton('MercadoPago - Pro', callback_data='pay_mp_pro')],
        [InlineKeyboardButton('Volver', callback_data='start')]
    ]
    await query.edit_message_text(
        plans_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_payment_stripe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tier = query.data.replace('pay_stripe_', '')
    prices = {'basic': 9, 'pro': 29, 'enterprise': 99}
    price = prices.get(tier, 0)
    if STRIPE_SECRET_KEY and not STRIPE_SECRET_KEY.startswith('sk_test_placeholder'):
        try:
            import stripe
            stripe.api_key = STRIPE_SECRET_KEY
            price_ids = {
                'basic': os.environ.get('STRIPE_PRICE_BASIC', ''),
                'pro': os.environ.get('STRIPE_PRICE_PRO', ''),
                'enterprise': os.environ.get('STRIPE_PRICE_ENTERPRISE', '')
            }
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{'price': price_ids.get(tier), 'quantity': 1}],
                mode='subscription',
                success_url=f'{BASE_URL}/payment/success',
                cancel_url=f'{BASE_URL}/payment/cancel',
                metadata={'user_id': str(update.effective_user.id), 'tier': tier}
            )
            keyboard = [[InlineKeyboardButton('Pagar Ahora', url=session.url)]]
            await query.edit_message_text(
                f'*Checkout Seguro - Stripe*\n\nPlan: *{tier.upper()}* - *${price}/mes*\n\n'
                f'Conexion SSL encriptada\nCancela cuando quieras\n\nHaz clic para pagar:',
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f'Error Stripe: {e}')
            await query.edit_message_text('Error procesando pago. Contacta @barbosasupport')
    else:
        await query.edit_message_text(
            f'*Plan {tier.upper()} - ${price}/mes*\n\n'
            'Para procesar el pago, contacta al administrador:\n'
            '@BarbosaAgencyProBot\n\n'
            'Stripe en configuracion.',
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Volver', callback_data='view_plans')]])
        )

async def handle_payment_mp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        '*MercadoPago - Pro $29/mes*\n\nMercadoPago en configuracion.\nContacta @BarbosaAgencyProBot',
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Volver', callback_data='view_plans')]])
    )

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    account_text = (
        f'*MI CUENTA*\n\n'
        f'Usuario: @{user.username or "N/A"}\n'
        f'Nombre: {user.first_name} {user.last_name or ""}\n'
        f'ID Telegram: `{user.id}`\n\n'
        f'Plan: *FREE* (actualiza para acceder a funciones premium)'
    )
    keyboard = [
        [InlineKeyboardButton('Actualizar Plan', callback_data='view_plans')],
        [InlineKeyboardButton('Menu Principal', callback_data='start')]
    ]
    await query.edit_message_text(
        account_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    if not is_admin(user.id):
        await query.answer('No autorizado', show_alert=True)
        return
    await query.answer()
    admin_text = (
        f'*PANEL ADMINISTRADOR*\n\n'
        f'Bot: @BarbosaAgencyProBot\n'
        f'Admin: {user.first_name}\n'
        f'Status: Activo\n'
        f'Deploy: Vercel\n'
    )
    keyboard = [
        [InlineKeyboardButton('Ver Usuarios', callback_data='admin_users')],
        [InlineKeyboardButton('Volver', callback_data='start')]
    ]
    await query.edit_message_text(
        admin_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton('Ver Planes', callback_data='view_plans')],
        [InlineKeyboardButton('Mi Cuenta', callback_data='my_account'),
         InlineKeyboardButton('Soporte', url='https://t.me/BarbosaAgencyProBot')]
    ]
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton('Panel Admin', callback_data='admin_panel')])
    await query.edit_message_text(
        f'*BARBOSA AGENCY PRO BOT*\n\nBienvenido de vuelta, {user.first_name}!\n\nQue deseas hacer?',
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ===================== SETUP HANDLERS =====================
def setup_handlers(application: Application):
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(view_plans, pattern='view_plans'))
    application.add_handler(CallbackQueryHandler(my_account, pattern='my_account'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(handle_payment_stripe, pattern='^pay_stripe_'))
    application.add_handler(CallbackQueryHandler(handle_payment_mp, pattern='^pay_mp_'))
    application.add_handler(CallbackQueryHandler(handle_back_to_start, pattern='^start$'))

# ===================== FLASK ROUTES =====================
@app.route('/')
def index():
    return jsonify({'status': 'Barbosa Agency Pro - Active', 'version': '2.0.0'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/payment/success')
def payment_success():
    return 'Pago completado! Revisa tu Telegram.', 200

@app.route('/payment/cancel')
def payment_cancel():
    return 'Pago cancelado. Intenta nuevamente desde el bot.', 200

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    application = get_application()
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, application.bot)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(application.initialize())
        loop.run_until_complete(application.process_update(update))
    finally:
        loop.close()
    return 'OK', 200

# ===================== MAIN (for polling mode) =====================
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    setup_handlers(application)
    logger.info('Bot iniciando en modo polling...')
    application.run_polling()

if __name__ == '__main__':
    main()
