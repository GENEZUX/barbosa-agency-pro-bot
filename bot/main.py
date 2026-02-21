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

# Financial Disclaimer
FINANCIAL_DISCLAIMER = """
Barbosa Agency Pro Bot es una *plataforma tecnologica*.
NO somos una institucion financiera, banco, ni prestamista directo.
*Terminos:* Todas las ofertas estan sujetas a aprobacion de credito.
Consulta con un asesor financiero antes de decidir.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admin_suffix = ' [ADMIN]' if is_admin(user.id) else ''
    keyboard = [
        [InlineKeyboardButton('Ver Planes', callback_data='view_plans')],
        [InlineKeyboardButton('Financiamiento', callback_data='financing_menu')],
        [InlineKeyboardButton('Mi Cuenta', callback_data='my_account'), InlineKeyboardButton('Soporte', url='https://t.me/BarbosaAgencyProBot')]
    ]
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton('Panel Admin', callback_data='admin')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        f"Hola {user.first_name}{admin_suffix}! "
        "*BARBOSA AGENCY PRO* "
        "Su plataforma de automatizacion y servicios inmobiliarios. "
        "Que desea hacer?"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'view_plans':
        await show_plans(query)
    elif data == 'financing_menu':
        await show_financing_menu(query)
    elif data == 'financing_agent':
        await show_agent_loan(query)
    elif data == 'financing_dscr':
        await query.edit_message_text("Usa el comando /dscr para iniciar la calculadora interactiva.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Volver', callback_data='financing_menu')]]))
    elif data == 'financing_seller':
        await show_seller_financing(query)
    elif data == 'back_main':
        await start(update, context)
    elif data == 'my_account':
        await show_account(query)
    elif data == 'admin':
        await show_admin(query)
    elif data.startswith('buy_'):
        tier = data.replace('buy_', '')
        await process_payment(query, tier)
    else:
        await query.edit_message_text('Opcion no disponible aun.')

async def show_financing_menu(query):
    keyboard = [
        [InlineKeyboardButton("Prestamo para Agente", callback_data='financing_agent')],
        [InlineKeyboardButton("Calculadora DSCR", callback_data='financing_dscr')],
        [InlineKeyboardButton("Financiamiento del Vendedor", callback_data='financing_seller')],
        [InlineKeyboardButton("Volver", callback_data='back_main')]
    ]
    text = (
        "*OPCIONES DE FINANCIAMIENTO SEGURO* "
        "Selecciona el servicio que necesitas: "
        "Prestamo para Agente: Capital basado en tus comisiones. "
        "Prestamos DSCR: Califica por la propiedad, no por tus ingresos. "
        "Financiamiento del Vendedor: Estrategias de MORE Seller Financing."
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_agent_loan(query):
    text = (
        "*PRESTAMO PARA AGENTES* "
        "Acceso a capital de trabajo: "
        "Transferencias mismo dia. "
        "Basado en tus comisiones futuras. "
        "Sin pagos fijos asfixiantes. "
        "Deseas verificar elegibilidad? "
        + FINANCIAL_DISCLAIMER
    )
    keyboard = [
        [InlineKeyboardButton("Verificar Elegibilidad", url="https://t.me/barbosa_finance")],
        [InlineKeyboardButton("Volver", callback_data='financing_menu')]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_seller_financing(query):
    text = (
        "*MORE SELLER FINANCING* "
        "Convierte hipotecas bajas en ventas rapidas: "
        "1. Vendedor mantiene su tasa baja. "
        "2. Comprador asume financiamiento flexible. "
        "3. Ventas en 48 horas en lugar de meses! "
        "Aprende a implementar esta estrategia con tus listings."
    )
    keyboard = [[InlineKeyboardButton("Volver", callback_data='financing_menu')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def dscr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "*CALCULADORA DSCR* "
        "Responde con: `/dscr_calc [valor] [pago] [renta]` "
        "Ejemplo: `/dscr_calc 300000 1800 2200`"
    )
    await update.message.reply_markdown(text)

async def dscr_calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 3:
        await update.message.reply_text("Usa: /dscr_calc [valor] [pago] [renta]")
        return
    try:
        val, pay, rent = map(float, context.args)
        dscr = rent / pay
        status = "EXCELENTE" if dscr >= 1.25 else "BUENO" if dscr >= 1.0 else "NO CALIFICA"
        response = (
            f"*RESULTADO DSCR* "
            f"*DSCR:* {dscr:.2f} "
            f"*Elegibilidad:* {status} "
            "*Basado en flujo de caja de la propiedad.*"
        )
        await update.message.reply_markdown(response)
    except:
        await update.message.reply_text("Error en los numeros ingresados.")

async def show_plans(query):
    keyboard = [
        [InlineKeyboardButton('BASIC $9/mes', callback_data='buy_basic')],
        [InlineKeyboardButton('PRO $29/mes', callback_data='buy_pro')],
        [InlineKeyboardButton('ENTERPRISE $99/mes', callback_data='buy_enterprise')],
        [InlineKeyboardButton('Volver', callback_data='back_main')]
    ]
    await query.edit_message_text('*Planes Disponibles*', reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_account(query):
    text = '*Mi Cuenta* Gestion de cuenta en desarrollo.'
    keyboard = [[InlineKeyboardButton('Volver', callback_data='back_main')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_admin(query):
    text = '*Panel Admin* Bienvenido al panel de administracion.'
    keyboard = [[InlineKeyboardButton('Volver', callback_data='back_main')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def process_payment(query, tier):
    text = f'*Plan {tier.upper()}* Contacta a @BarbosaAgencyProBot para el pago.'
    keyboard = [[InlineKeyboardButton('Volver', callback_data='view_plans')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# Telegram app global
ptb_app = None

async def get_ptb_app():
    global ptb_app
    if ptb_app is None:
        ptb_app = Application.builder().token(TELEGRAM_TOKEN).build()
        ptb_app.add_handler(CommandHandler('start', start))
        ptb_app.add_handler(CommandHandler('dscr', dscr_command))
        ptb_app.add_handler(CommandHandler('dscr_calc', dscr_calc_command))
        ptb_app.add_handler(CallbackQueryHandler(handle_callback))
        await ptb_app.initialize()
    return ptb_app

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_process_update())
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

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'bot': 'Barbosa Agency Pro Bot'})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
