import os
import logging
from flask import Flask, request, jsonify
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler,
    MessageHandler, Filters, CallbackContext
)
from datetime import datetime
from bot.utils.config import config
from bot.models.base import init_db, db_session
from bot.models.user import User
from bot.models.payment import Payment
from bot.services.stripe_service import StripeService
from bot.services.mp_service import MercadoPagoService
import sqlalchemy as db

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
app.secret_key = config.SECRET_KEY
bot = Bot(config.TELEGRAM_TOKEN)


# ===================== HELPERS =====================
def get_or_create_user(update: Update) -> User:
    telegram_user = update.effective_user
    user = User.query.filter_by(telegram_id=telegram_user.id).first()
    if not user:
        user = User(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language_code=telegram_user.language_code
        )
        db_session.add(user)
        db_session.commit()
        logger.info(f'Nuevo usuario creado: {telegram_user.id}')
    return user


# ===================== HANDLERS =====================
def start(update: Update, context: CallbackContext):
    user = get_or_create_user(update)
    status_emoji = '' if user.subscription_status == 'active' else ''
    keyboard = [
        [InlineKeyboardButton(' Ver Planes', callback_data='view_plans')],
        [InlineKeyboardButton(' Mi Cuenta', callback_data='my_account'),
         InlineKeyboardButton(' Soporte', url='https://t.me/barbosasupport')]
    ]
    if user.is_admin:
        keyboard.append([InlineKeyboardButton(' Panel Admin', callback_data='admin_panel')])

    welcome_text = (
        f'Hola {user.first_name or "Cliente"}! {status_emoji}\n\n'
        f'*BARBOSA AGENCY BOT*\n'
        f'Tu asistente de automatizacion profesional.\n\n'
        f'Plan actual: *{user.subscription_tier.upper()}*\n'
        f'Estado: *{user.subscription_status}*\n\n'
        f'Que deseas hacer hoy?'
    )
    update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


def view_plans(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    plans_text = (
        '*PLANES BARBOSA AGENCY*\n\n'
        ' *BASICO - $9/mes*\n'
        '  1 proyecto activo\n'
        '  Soporte email 48h\n'
        '  Reportes mensuales\n\n'
        ' *PRO - $29/mes* _(Popular)_\n'
        '  5 proyectos activos\n'
        '  Soporte prioritario 24h\n'
        '  Automatizaciones ilimitadas\n'
        '  API access\n\n'
        ' *ENTERPRISE - $99/mes*\n'
        '  Proyectos ilimitados\n'
        '  Soporte 24/7 WhatsApp\n'
        '  Desarrollo custom\n'
        '  SLA garantizado\n'
    )

    keyboard = []
    if config.ENABLE_STRIPE:
        keyboard.append([
            InlineKeyboardButton(' Stripe - Basic $9', callback_data='pay_stripe_basic'),
            InlineKeyboardButton(' Stripe - Pro $29', callback_data='pay_stripe_pro')
        ])
        keyboard.append([
            InlineKeyboardButton(' Stripe - Enterprise $99', callback_data='pay_stripe_enterprise')
        ])
    if config.ENABLE_MP:
        keyboard.append([
            InlineKeyboardButton(' MercadoPago - Pro', callback_data='pay_mp_pro')
        ])
    keyboard.append([InlineKeyboardButton(' Volver', callback_data='start')])

    query.edit_message_text(
        plans_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


def handle_payment_stripe(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    tier = query.data.replace('pay_stripe_', '')
    user = get_or_create_user(update)
    try:
        session = StripeService.create_checkout_session(user, tier, mode='subscription')
        keyboard = [[InlineKeyboardButton(' Pagar Ahora', url=session['url'])]]
        query.edit_message_text(
            f'*Checkout Seguro - Stripe*\n\n'
            f'Plan: *{tier.upper()}*\n'
            f'Precio: *${StripeService.TIER_AMOUNTS.get(tier, 0)}/mes*\n\n'
            f'Conexion SSL encriptada\n'
            f'Cancela cuando quieras\n\n'
            f'Haz clic para completar el pago:',
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f'Error creando sesion Stripe: {e}')
        query.edit_message_text('Error procesando pago. Contacta soporte @barbosasupport')


def handle_payment_mp(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    tier = query.data.replace('pay_mp_', '')
    user = get_or_create_user(update)
    try:
        preference = MercadoPagoService.create_preference(user, tier)
        keyboard = [[InlineKeyboardButton(' Pagar con MercadoPago', url=preference['init_point'])]]
        query.edit_message_text(
            f'*Checkout - MercadoPago*\n\n'
            f'Plan: *{tier.upper()}*\n'
            f'Acepta todas las tarjetas\n'
            f'Pago en efectivo disponible\n\n'
            f'Haz clic para pagar:',
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f'Error creando preferencia MP: {e}')
        query.edit_message_text('Error con MercadoPago. Intenta con Stripe.')


def my_account(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user = get_or_create_user(update)
    total_payments = Payment.query.filter_by(user_id=user.id, status='completed').count()
    total_spent = db_session.query(db.func.sum(Payment.amount)).filter(
        Payment.user_id == user.id, Payment.status == 'completed'
    ).scalar() or 0

    account_text = (
        f'*MI CUENTA*\n\n'
        f'ID: `{user.telegram_id}`\n'
        f'Email: {user.email or "No configurado"}\n'
        f'Plan: *{user.subscription_tier.upper()}*\n'
        f'Estado: *{user.subscription_status}*\n'
        f'Total pagado: *${float(total_spent):.2f}*\n'
        f'Pagos realizados: *{total_payments}*'
    )
    keyboard = [
        [InlineKeyboardButton(' Actualizar Plan', callback_data='view_plans')],
        [InlineKeyboardButton(' Menu Principal', callback_data='start')]
    ]
    query.edit_message_text(
        account_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


def admin_panel(update: Update, context: CallbackContext):
    query = update.callback_query
    user = get_or_create_user(update)
    if not user.is_admin:
        query.answer('No autorizado', show_alert=True)
        return
    query.answer()
    total_users = User.query.count()
    active_subs = User.query.filter_by(subscription_status='active').count()
    monthly_revenue = db_session.query(db.func.sum(Payment.amount)).filter(
        Payment.status == 'completed',
        Payment.created_at >= datetime.utcnow().replace(day=1)
    ).scalar() or 0

    admin_text = (
        f'*PANEL ADMINISTRADOR*\n\n'
        f'Usuarios totales: *{total_users}*\n'
        f'Suscripciones activas: *{active_subs}*\n'
        f'Ingresos este mes: *${float(monthly_revenue):.2f}*\n'
    )
    keyboard = [
        [InlineKeyboardButton(' Web Dashboard', url=f'{config.BASE_URL}/admin')],
        [InlineKeyboardButton(' Volver', callback_data='start')]
    ]
    query.edit_message_text(
        admin_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


# ===================== WEBHOOKS =====================
@app.route('/')
def index():
    return jsonify({
        'status': 'Barbosa Agency Pro - Active',
        'version': '2.0.0',
        'stripe': config.ENABLE_STRIPE,
        'mercadopago': config.ENABLE_MP
    })


@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200


@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    result, data = StripeService.process_webhook(payload, sig_header)
    return jsonify({'status': result}), 200 if result == 'success' else 400


@app.route('/webhook/mercadopago', methods=['POST'])
def mp_webhook():
    data = request.json or request.form.to_dict()
    MercadoPagoService.process_webhook(data)
    return jsonify({'status': 'processed'}), 200


@app.route('/payment/success')
def payment_success():
    return 'Pago completado! Revisa tu Telegram para la confirmacion.', 200


@app.route('/payment/cancel')
def payment_cancel():
    return 'Pago cancelado. Puedes intentarlo nuevamente desde el bot.', 200


@app.route(f'/{config.TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'OK', 200


# ===================== SETUP =====================
def setup_bot():
    global dispatcher
    updater = Updater(config.TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Command handlers
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('admin', admin_panel))

    # Callback handlers
    dispatcher.add_handler(CallbackQueryHandler(view_plans, pattern='view_plans'))
    dispatcher.add_handler(CallbackQueryHandler(my_account, pattern='my_account'))
    dispatcher.add_handler(CallbackQueryHandler(admin_panel, pattern='admin_panel'))
    dispatcher.add_handler(CallbackQueryHandler(handle_payment_stripe, pattern='^pay_stripe_'))
    dispatcher.add_handler(CallbackQueryHandler(handle_payment_mp, pattern='^pay_mp_'))
    dispatcher.add_handler(CallbackQueryHandler(start, pattern='start'))

    return updater


def main():
    init_db()
    logger.info('Base de datos inicializada')
    updater = setup_bot()

    if config.BASE_URL and 'railway' in config.BASE_URL.lower():
        PORT = int(os.environ.get('PORT', 5000))
        webhook_url = f'{config.BASE_URL}/{config.TELEGRAM_TOKEN}'
        updater.start_webhook(
            listen='0.0.0.0',
            port=PORT,
            url_path=config.TELEGRAM_TOKEN,
            webhook_url=webhook_url
        )
        logger.info(f'Webhook activo en {webhook_url}')
        app.run(host='0.0.0.0', port=PORT, threaded=True)
    else:
        updater.start_polling()
        logger.info('Bot en modo polling (desarrollo)')
        updater.idle()


if __name__ == '__main__':
    main()
