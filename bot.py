import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import random
import time
from pymongo import MongoClient
from datetime import datetime
import pytz
import string
import os


from telebot import apihelper apihelper.ENABLE_MIDDLEWARE = True

# Bot token
TOKEN = os.getenv("TOKEN")

# MongoDB connection
MONGODB_USER = os.getenv("DB_USER")
MONGODB_PASSWORD = os.getenv("DB_PASS")
MONGODB_CLUSTER = os.getenv("DB_CLUSTER")

client = MongoClient(f"mongodb+srv://{MONGODB_USER}:{MONGODB_PASSWORD}@{MONGODB_CLUSTER}/")
db = client['bank_bot']
users_collection = db['users']
transactions_collection = db['transactions']
bot_stats_collection = db['bot_stats']
transfer_requests_collection = db['transfer_requests']

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

def generate_transaction_id(user_id, is_transfer=False):
    year = datetime.now(baghdad_tz).strftime("%y")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    if is_transfer:
        return f"IQ{year}-{user_id}-{random_part}"
    else:
        return f"IQ{year}-{random_part}"

def log_transaction(user_id, transaction_type, amount, details=None, transaction_id=None):
    if not transaction_id:
        transaction_id = generate_transaction_id(user_id)
    transaction = {
        'transaction_id': transaction_id,
        'user_id': user_id,
        'type': transaction_type,
        'amount': amount,
        'timestamp': get_current_time(),
        'details': details
    }
    transactions_collection.insert_one(transaction)
    return transaction_id

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

# Keyboard markup
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton('💰 رصيدي'), KeyboardButton('📜 العمليات السابقة'))
    keyboard.row(KeyboardButton('🏦 سيولة البوت'), KeyboardButton('💸 تحويل'))
    keyboard.row(KeyboardButton('🎁 الهدية اليومية'))
    return keyboard

# Error handling wrapper
def send_message_safely(chat_id, text, **kwargs):
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except telebot.apihelper.ApiException as e:
        print(f"Error sending message to {chat_id}: {e}")

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    send_message_safely(user_id, "👋 مرحبًا بك في البوت البنكي! يمكنك استخدام الأزرار أدناه للتحكم.", reply_markup=get_main_keyboard())

# Balance command
@bot.message_handler(func=lambda message: message.text == '💰 رصيدي')
def check_balance(message):
    user_id = message.from_user.id
    balance = get_user_balance(user_id)
    response = f"💰 رصيدك الحالي: ${balance:.2f}\n\n🆔 رقم حسابك (معرف المستخدم): `{user_id}`"
    send_message_safely(user_id, response, parse_mode='Markdown')

# Transaction history command
@bot.message_handler(func=lambda message: message.text == '📜 العمليات السابقة')
def transaction_history(message):
    user_id = message.from_user.id
    transactions = get_transaction_history(user_id)
    if not transactions:
        send_message_safely(user_id, "📭 لا توجد عمليات سابقة.")
        return
    
    history = "📜 سجل العمليات:\n\n"
    for transaction in transactions:
        date = transaction['timestamp'].strftime("%I:%M:%S %p %d/%m/%Y")
        transaction_id = transaction['transaction_id']
        if transaction['type'] == 'transfer_out':
            history += f"🔸 {date}: تحويل ${transaction['amount']:.2f} إلى {transaction['details']['recipient_id']}\n   🆔 رقم العملية: `{transaction_id}`\n\n"
        elif transaction['type'] == 'transfer_in':
            history += f"🔹 {date}: استلام ${transaction['amount']:.2f} من {transaction['details']['sender_id']}\n   🆔 رقم العملية: `{transaction_id}`\n\n"
        elif transaction['type'] == 'daily_gift':
            history += f"🎁 {date}: هدية يومية ${transaction['amount']:.2f}\n   🆔 رقم العملية: `{transaction_id}`\n\n"
    
    send_message_safely(user_id, history, parse_mode='Markdown')

# Bot liquidity command
@bot.message_handler(func=lambda message: message.text == '🏦 سيولة البوت')
def bot_liquidity(message):
    user_id = message.from_user.id
    liquidity = get_bot_liquidity()
    total_user_balance = get_total_user_balance()
    
    response = (
        f"🏦 سيولة البوت الحالية: ${liquidity:.2f}\n"
        f"💰 إجمالي أرصدة المستخدمين: ${total_user_balance:.2f}\n"
    )
    
    send_message_safely(user_id, response)

# Transfer command
@bot.message_handler(func=lambda message: message.text == '💸 تحويل')
def transfer_start(message):
    user_id = message.from_user.id
    send_message_safely(user_id, "🔢 أدخل رقم حساب المستلم (معرف المستخدم):")
    bot.register_next_step_handler(message, transfer_amount)

def transfer_amount(message):
    user_id = message.from_user.id
    recipient_id = message.text
    if not recipient_id.isdigit():
        send_message_safely(user_id, "❌ رقم الحساب غير صحيح. يرجى إدخال رقم صحيح.")
        return
    recipient_id = int(recipient_id)
    if recipient_id == user_id:
        send_message_safely(user_id, "❌ لا يمكنك التحويل لنفسك. يرجى إدخال رقم حساب آخر.")
        return
    send_message_safely(user_id, "💲 أدخل المبلغ المراد تحويله:")
    bot.register_next_step_handler(message, transfer_confirm, recipient_id)

def transfer_confirm(message, recipient_id):
    user_id = message.from_user.id
    try:
        amount = float(message.text)
    except ValueError:
        send_message_safely(user_id, "❌ مبلغ غير صحيح. يرجى إدخال رقم.")
        return
    
    fee = amount * 0.02
    total_amount = amount + fee
    user_balance = get_user_balance(user_id)
    
    if total_amount > user_balance:
        send_message_safely(user_id, "❌ رصيدك غير كافٍ لإتمام هذه العملية.")
        return
    
    transfer_id = generate_transaction_id(user_id, is_transfer=True)
    confirm_message = f"📝 تأكيد التحويل:\nالمبلغ: ${amount:.2f}\nالرسوم: ${fee:.2f}\nالإجمالي: ${total_amount:.2f}\nالمستلم: {recipient_id}\n\n🆔 رقم العملية: `{transfer_id}`"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("✅ تأكيد", callback_data=f"confirm_transfer:{transfer_id}"),
                 InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_transfer:{transfer_id}"))
    
    send_message_safely(user_id, confirm_message, reply_markup=keyboard, parse_mode='Markdown')
    
    # Store transfer request
    transfer_requests_collection.insert_one({
        'transfer_id': transfer_id,
        'sender_id': user_id,
        'recipient_id': recipient_id,
        'amount': amount,
        'fee': fee,
        'status': 'pending',
        'timestamp': get_current_time()
    })

@bot.callback_query_handler(func=lambda call: call.data.startswith(('confirm_transfer', 'cancel_transfer')))
def transfer_callback(call):
    user_id = call.from_user.id
    action, transfer_id = call.data.split(':')
    
    transfer_request = transfer_requests_collection.find_one({'transfer_id': transfer_id})
    if not transfer_request or transfer_request['sender_id'] != user_id:
        bot.answer_callback_query(call.id, "❌ عملية التحويل غير صالحة أو منتهية الصلاحية.")
        return

    if action == 'confirm_transfer':
        perform_transfer(transfer_request)
        bot.answer_callback_query(call.id, "✅ تم تأكيد عملية التحويل.")
    else:
        transfer_requests_collection.delete_one({'transfer_id': transfer_id})
        bot.answer_callback_query(call.id, "❌ تم إلغاء عملية التحويل.")

def perform_transfer(transfer_request):
    sender_id = transfer_request['sender_id']
    recipient_id = transfer_request['recipient_id']
    amount = transfer_request['amount']
    fee = transfer_request['fee']
    total_amount = amount + fee
    transfer_id = transfer_request['transfer_id']

    sender_balance = get_user_balance(sender_id)
    recipient_balance = get_user_balance(recipient_id)

    if total_amount > sender_balance:
        send_message_safely(sender_id, "❌ رصيدك غير كافٍ لإتمام هذه العملية.")
        return

    update_user_balance(sender_id, sender_balance - total_amount)
    update_user_balance(recipient_id, recipient_balance + amount)
    update_bot_liquidity(fee)

    log_transaction(sender_id, 'transfer_out', -total_amount, {'recipient_id': recipient_id, 'transfer_id': transfer_id}, transfer_id)
    log_transaction(recipient_id, 'transfer_in', amount, {'sender_id': sender_id, 'transfer_id': transfer_id}, transfer_id)

    send_message_safely(sender_id, f"✅ تم التحويل بنجاح. المبلغ: ${amount:.2f}, الرسوم: ${fee:.2f}\n🆔 رقم العملية: `{transfer_id}`", parse_mode='Markdown')
    send_message_safely(recipient_id, f"💰 لقد استلمت تحويلاً بقيمة ${amount:.2f}\n🆔 رقم العملية: `{transfer_id}`", parse_mode='Markdown')

    transfer_requests_collection.delete_one({'transfer_id': transfer_id})

# Daily gift command
@bot.message_handler(func=lambda message: message.text == '🎁 الهدية اليومية')
def daily_gift(message):
    user_id = message.from_user.id
    user = users_collection.find_one({'user_id': user_id})
    
    current_time = get_current_time()
    if user and 'last_gift' in user:
        last_gift = user['last_gift'].replace(tzinfo=baghdad_tz)
        if (current_time - last_gift).days < 1:
            send_message_safely(user_id, "⏳ لقد حصلت بالفعل على هديتك اليومية. يرجى المحاولة غدًا.")
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
    
    transaction_id = log_transaction(user_id, 'daily_gift', gift_amount)
    
    response = (
        f"🎉 مبروك! لقد حصلت على هدية يومية بقيمة ${gift_amount:.3f}\n"
        f"💰 رصيدك الجديد: ${new_balance:.2f}\n"
        f"🆔 رقم العملية: `{transaction_id}`"
    )
    send_message_safely(user_id, response, parse_mode='Markdown')

# Error handling
@bot.middleware_handler(update_types=['message'])
def handle_message(bot_instance, message):
    try:
        bot_instance.process_new_messages([message])
    except Exception as e:
        user_id = message.from_user.id
        error_message = f"حدث خطأ أثناء معالجة طلبك. الرجاء المحاولة مرة أخرى لاحقًا."
        send_message_safely(user_id, error_message)
        print(f"Error processing message: {e}")

# Main function to run the bot
def main():
    print("Starting the bot...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Bot polling error: {e}")
            time.sleep(15)

if __name__ == '__main__':
    main()
