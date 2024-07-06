import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import random
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz


# Bot token
TOKEN = os.getenv("TOKEN")

# MongoDB connection
MONGODB_USER = 'dataBase'
MONGODB_PASSWORD 'D9bzaZUaqEDSmBZn'
MONGODB_CLUSTER = 'cluster0.if1idei.mongodb.net'

client = MongoClient(f"mongodb+srv://{MONGODB_USER}:{MONGODB_PASSWORD}@{MONGODB_CLUSTER}/")
db = client['bank_bot']
users_collection = db['users']
transactions_collection = db['transactions']
bot_stats_collection = db['bot_stats']

bot = telebot.TeleBot(TOKEN)

# Baghdad timezone
baghdad_tz = pytz.timezone('Asia/Baghdad')

# Helper functions
def get_current_time():
    return datetime.now(baghdad_tz)

def get_user_balance(user_id):
    user = users_collection.find_one({'user_id': user_id})
    return user['balance'] if user else 0

def update_user_balance(user_id, new_balance):
    users_collection.update_one(
        {'user_id': user_id},
        {'$set': {'balance': new_balance}},
        upsert=True
    )

def log_transaction(user_id, transaction_type, amount, details=None):
    transaction = {
        'user_id': user_id,
        'type': transaction_type,
        'amount': amount,
        'timestamp': get_current_time(),
        'details': details
    }
    transactions_collection.insert_one(transaction)

def get_transaction_history(user_id):
    transactions = transactions_collection.find({'user_id': user_id})
    return list(transactions)

def update_bot_liquidity(amount):
    current_time = get_current_time()
    bot_stats_collection.update_one(
        {'_id': 'liquidity'},
        {
            '$inc': {'amount': amount},
            '$push': {
                'history': {
                    'amount': amount,
                    'timestamp': current_time
                }
            }
        },
        upsert=True
    )

def get_bot_liquidity():
    stats = bot_stats_collection.find_one({'_id': 'liquidity'})
    return stats['amount'] if stats else 0

def get_total_user_balance():
    total = sum(user['balance'] for user in users_collection.find())
    return total

def calculate_hourly_change():
    now = get_current_time()
    one_hour_ago = now - timedelta(hours=1)
    
    current_liquidity = get_bot_liquidity()
    past_liquidity = bot_stats_collection.find_one(
        {'_id': 'liquidity', 'history.timestamp': {'$lte': one_hour_ago}},
        sort=[('history.timestamp', -1)]
    )
    
    if past_liquidity and past_liquidity['history']:
        past_amount = next((h['amount'] for h in reversed(past_liquidity['history']) if h['timestamp'] <= one_hour_ago), None)
        if past_amount is not None:
            change = ((current_liquidity - past_amount) / past_amount) * 100
            return change
    
    return 0  # If no past data or error, return 0% change

# Keyboard markup
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton('💰 رصيدي'), KeyboardButton('📜 العمليات السابقة'))
    keyboard.row(KeyboardButton('🏦 سيولة البوت'), KeyboardButton('💸 تحويل'))
    keyboard.row(KeyboardButton('🎁 الهدية اليومية'))
    return keyboard

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    bot.send_message(user_id, "👋 مرحبًا بك في البوت البنكي! يمكنك استخدام الأزرار أدناه للتحكم.", reply_markup=get_main_keyboard())

# Balance command
@bot.message_handler(func=lambda message: message.text == '💰 رصيدي')
def check_balance(message):
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    response = f"💰 رصيدك الحالي: ${balance:.2f}\n\n🆔 رقم حسابك (معرف المستخدم): `{user_id}`"
    bot.send_message(user_id, response, parse_mode='Markdown')

# Transaction history command
@bot.message_handler(func=lambda message: message.text == '📜 العمليات السابقة')
def transaction_history(message):
    user_id = message.from_user.id
    transactions = get_transaction_history(user_id)
    if not transactions:
        bot.send_message(user_id, "📭 لا توجد عمليات سابقة.")
        return
    
    history = "📜 سجل العمليات:\n\n"
    for transaction in transactions:
        date = transaction['timestamp'].strftime("%I:%M:%S %p %d/%m/%Y")
        if transaction['type'] == 'transfer_out':
            history += f"🔸 {date}: تحويل ${transaction['amount']:.2f} إلى {transaction['details']['recipient_id']}\n"
        elif transaction['type'] == 'transfer_in':
            history += f"🔹 {date}: استلام ${transaction['amount']:.2f} من {transaction['details']['sender_id']}\n"
        elif transaction['type'] == 'daily_gift':
            history += f"🎁 {date}: هدية يومية ${transaction['amount']:.2f}\n"
    
    bot.send_message(user_id, history)

# Bot liquidity command
@bot.message_handler(func=lambda message: message.text == '🏦 سيولة البوت')
def bot_liquidity(message):
    user_id = message.from_user.id
    liquidity = get_bot_liquidity()
    total_user_balance = get_total_user_balance()
    hourly_change = calculate_hourly_change()
    
    response = (
        f"🏦 سيولة البوت الحالية: ${liquidity:.2f}\n"
        f"💰 إجمالي أرصدة المستخدمين: ${total_user_balance:.2f}\n"
        f"📊 نسبة التغير في الساعة الأخيرة: {hourly_change:.2f}%"
    )
    
    bot.send_message(user_id, response)

# Transfer command
@bot.message_handler(func=lambda message: message.text == '💸 تحويل')
def transfer_start(message):
    user_id = message.from_user.id
    bot.send_message(user_id, "🔢 أدخل رقم حساب المستلم (معرف المستخدم):")
    bot.register_next_step_handler(message, transfer_amount)

def transfer_amount(message):
    user_id = message.from_user.id
    recipient_id = message.text
    if not recipient_id.isdigit():
        bot.send_message(user_id, "❌ رقم الحساب غير صحيح. يرجى إدخال رقم صحيح.")
        return
    recipient_id = int(recipient_id)
    if recipient_id == user_id:
        bot.send_message(user_id, "❌ لا يمكنك التحويل لنفسك. يرجى إدخال رقم حساب آخر.")
        return
    bot.send_message(user_id, "💲 أدخل المبلغ المراد تحويله:")
    bot.register_next_step_handler(message, transfer_confirm, recipient_id)

def transfer_confirm(message, recipient_id):
    user_id = message.from_user.id
    try:
        amount = float(message.text)
    except ValueError:
        bot.send_message(user_id, "❌ مبلغ غير صحيح. يرجى إدخال رقم.")
        return
    
    fee = amount * 0.02
    total_amount = amount + fee
    user_balance = get_user_balance(user_id)
    
    if total_amount > user_balance:
        bot.send_message(user_id, "❌ رصيدك غير كافٍ لإتمام هذه العملية.")
        return
    
    confirm_message = f"📝 تأكيد التحويل:\nالمبلغ: ${amount:.2f}\nالرسوم: ${fee:.2f}\nالإجمالي: ${total_amount:.2f}\nالمستلم: {recipient_id}"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("✅ تأكيد", callback_data=f"confirm_transfer:{recipient_id}:{amount}"),
                 InlineKeyboardButton("❌ إلغاء", callback_data="cancel_transfer"))
    
    bot.send_message(user_id, confirm_message, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('confirm_transfer', 'cancel_transfer')))
def transfer_callback(call):
    user_id = call.from_user.id
    if call.data.startswith('confirm_transfer'):
        _, recipient_id, amount = call.data.split(':')
        recipient_id = int(recipient_id)
        amount = float(amount)
        verification_code = ''.join([str(random.randint(0, 9)) for _ in range(4)])
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, f"🔐 رمز التحقق هو: {verification_code}\nيرجى إدخال الرمز للتأكيد:")
        bot.register_next_step_handler(call.message, transfer_execute, recipient_id, amount, verification_code)
    else:
        bot.answer_callback_query(call.id, "❌ تم إلغاء عملية التحويل.")
        bot.send_message(user_id, "❌ تم إلغاء عملية التحويل.")

def transfer_execute(message, recipient_id, amount, verification_code):
    user_id = message.from_user.id
    if message.text != verification_code:
        bot.send_message(user_id, "❌ رمز التحقق غير صحيح. تم إلغاء العملية.")
        return
    
    fee = amount * 0.02
    total_amount = amount + fee
    user_balance = get_user_balance(user_id)
    recipient_balance = get_user_balance(recipient_id)
    
    if total_amount > user_balance:
        bot.send_message(user_id, "❌ رصيدك غير كافٍ لإتمام هذه العملية.")
        return
    
    update_user_balance(user_id, user_balance - total_amount)
    update_user_balance(recipient_id, recipient_balance + amount)
    
    update_bot_liquidity(fee)
    
    log_transaction(user_id, 'transfer_out', -total_amount, {'recipient_id': recipient_id})
    log_transaction(recipient_id, 'transfer_in', amount, {'sender_id': user_id})
    
    bot.send_message(user_id, f"✅ تم التحويل بنجاح. المبلغ: ${amount:.2f}, الرسوم: ${fee:.2f}")
    bot.send_message(recipient_id, f"💰 لقد استلمت تحويلاً بقيمة ${amount:.2f}")

    # Simulate processing delay
    time.sleep(2)
    bot.send_message(user_id, "✅ تمت معالجة التحويل بنجاح!")

# Daily gift command
@bot.message_handler(func=lambda message: message.text == '🎁 الهدية اليومية')
def daily_gift(message):
    user_id = message.from_user.id
    user = users_collection.find_one({'user_id': user_id})
    
    current_time = get_current_time()
    if user and 'last_gift' in user:
        last_gift = user['last_gift'].replace(tzinfo=baghdad_tz)
        if (current_time - last_gift).days < 1:
            bot.send_message(user_id, "⏳ لقد حصلت بالفعل على هديتك اليومية. يرجى المحاولة غدًا.")
            return
    
    gift_amount = random.uniform(0.005, 0.01)
    current_balance = get_user_balance(user_id)
    new_balance = current_balance + gift_amount
    
    update_user_balance(user_id, new_balance)
    users_collection.update_one(
        {'user_id': user_id},
        {'$set': {'last_gift': current_time}},
        upsert=True
    )
    
    log_transaction(user_id, 'daily_gift', gift_amount)
    
    bot.send_message(user_id, f"🎉 مبروك! لقد حصلت على هدية يومية بقيمة ${gift_amount:.3f}")

# Run the bot
bot.polling()
