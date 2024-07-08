import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import random
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz
import string
import requests
import os

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
loans_collection = db['loans']

bot = telebot.TeleBot(TOKEN)

# Baghdad timezone
baghdad_tz = pytz.timezone('Asia/Baghdad')

# Bot start time
BOT_START_TIME = datetime.now(baghdad_tz)

# Helper functions
def get_current_time():
    return datetime.now(baghdad_tz)

def get_uptime():
    uptime = get_current_time() - BOT_START_TIME
    days, remainder = divmod(uptime.total_seconds(), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{int(days)} يوم, {int(hours)} ساعة, {int(minutes)} دقيقة"

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
    log_transaction(None, 'bot_liquidity_change', amount, {'type': 'system'})

def get_bot_liquidity():
    stats = bot_stats_collection.find_one({'_id': 'liquidity'})
    if not stats:
        initial_liquidity = 100
        bot_stats_collection.insert_one({'_id': 'liquidity', 'amount': initial_liquidity})
        return initial_liquidity
    return stats['amount']

def get_total_user_balance():
    total = sum(user['balance'] for user in users_collection.find())
    return total

def send_message_safely(chat_id, text, **kwargs):
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")

# Keyboard markup
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton('💰 رصيدي'), KeyboardButton('📜 العمليات السابقة'))
    keyboard.row(KeyboardButton('🏦 سيولة البوت'), KeyboardButton('💸 تحويل'))
    keyboard.row(KeyboardButton('🎮 أخرى'))
    return keyboard

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    send_message_safely(user_id, "👋 مرحبًا بك في البوت البنكي! يمكنك استخدام الأزرار أدناه للتحكم.", reply_markup=get_main_keyboard())

# Handle all text messages
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text

    if text == '💰 رصيدي':
        check_balance(user_id)
    elif text == '📜 العمليات السابقة':
        transaction_history(user_id)
    elif text == '🏦 سيولة البوت':
        bot_liquidity(user_id)
    elif text == '💸 تحويل':
        transfer_start(user_id)
    elif text == '🎮 أخرى':
        show_other_options(user_id)
    else:
        send_message_safely(user_id, "عذرًا، لم أفهم هذا الأمر. يرجى استخدام الأزرار المتاحة.")

def check_balance(user_id):
    balance = get_user_balance(user_id)
    loans = get_user_loans(user_id)
    total_loan = sum(loan['amount'] + loan['interest'] for loan in loans if not loan['paid'])
    
    response = f"💰 رصيدك الحالي: ${balance:.2f}\n"
    if total_loan > 0:
        response += f"💸 إجمالي القروض المستحقة: ${total_loan:.2f}\n"
    response += f"🆔 رقم حسابك (معرف المستخدم): `{user_id}`"
    
    send_message_safely(user_id, response, parse_mode='Markdown')

def transaction_history(user_id):
    transactions = get_transaction_history(user_id)
    if not transactions:
        send_message_safely(user_id, "📭 لا توجد عمليات سابقة.")
        return
    
    history = "📜 سجل العمليات:\n\n"
    for transaction in transactions:
        date = transaction['timestamp'].strftime("%H:%M:%S %d/%m/%Y")
        transaction_id = transaction['transaction_id']
        if transaction['type'] == 'transfer_out':
            history += f"🔸 {date}: تحويل ${transaction['amount']:.2f} إلى {transaction['details']['recipient_id']}\n   🆔 رقم العملية: `{transaction_id}`\n\n"
        elif transaction['type'] == 'transfer_in':
            history += f"🔹 {date}: استلام ${transaction['amount']:.2f} من {transaction['details']['sender_id']}\n   🆔 رقم العملية: `{transaction_id}`\n\n"
        elif transaction['type'] == 'daily_gift':
            history += f"🎁 {date}: هدية يومية ${transaction['amount']:.2f}\n   🆔 رقم العملية: `{transaction_id}`\n\n"
        elif transaction['type'] in ['slots_win', 'slots_loss']:
            action = "ربح" if transaction['type'] == 'slots_win' else "خسارة"
            history += f"🎰 {date}: {action} في Slots ${abs(transaction['amount']):.2f}\n   🆔 رقم العملية: `{transaction_id}`\n\n"
        elif transaction['type'] == 'loan':
            history += f"💸 {date}: قرض ${transaction['amount']:.2f}\n   🆔 رقم العملية: `{transaction_id}`\n\n"
        elif transaction['type'] == 'loan_repayment':
            history += f"💰 {date}: سداد قرض ${transaction['amount']:.2f}\n   🆔 رقم العملية: `{transaction_id}`\n\n"
    
    send_message_safely(user_id, history, parse_mode='Markdown')

def bot_liquidity(user_id):
    liquidity = get_bot_liquidity()
    total_user_balance = get_total_user_balance()
    
    response = (
        f"🏦 سيولة البوت الحالية: ${liquidity:.2f}\n"
        f"💰 إجمالي أرصدة المستخدمين: ${total_user_balance:.2f}\n"
    )
    
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("📊 الحالة", callback_data="check_status"))
    
    send_message_safely(user_id, response, reply_markup=keyboard)

def transfer_start(user_id):
    send_message_safely(user_id, "🔢 أدخل رقم حساب المستلم (معرف المستخدم):")
    bot.register_next_step_handler_by_chat_id(user_id, transfer_amount)

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
    bot.register_next_step_handler_by_chat_id(user_id, transfer_confirm, recipient_id)

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

def show_other_options(user_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("🎁 الهدية اليومية", callback_data="daily_gift"),
                 InlineKeyboardButton("🎰 لعبة Slots", callback_data="play_slots"))
    keyboard.row(InlineKeyboardButton("💸 القرض", callback_data="loan_options"))
    send_message_safely(user_id, "اختر إحدى الخيارات التالية:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data in ["daily_gift", "play_slots", "loan_options"])
def other_options_callback(call):
    user_id = call.from_user.id
    if call.data == "daily_gift":
        daily_gift(user_id)
    elif call.data == "play_slots":
        start_slots_game(user_id)
    elif call.data == "loan_options":
        show_loan_options(user_id)
    bot.answer_callback_query(call.id)

def daily_gift(user_id):
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

def start_slots_game(user_id):
    send_message_safely(user_id, "أدخل مبلغ الرهان (من 5$ إلى 100$):")
    bot.register_next_step_handler_by_chat_id(user_id, process_slots_bet)

def process_slots_bet(message):
    user_id = message.from_user.id
    try:
        bet_amount = float(message.text)
        if 5 <= bet_amount <= 100:
            play_slots(user_id, bet_amount)
        else:
            send_message_safely(user_id, "المبلغ يجب أن يكون بين 5$ و 100$. حاول مرة أخرى.")
            start_slots_game(user_id)
    except ValueError:
        send_message_safely(user_id, "الرجاء إدخال رقم صحيح. حاول مرة أخرى.")
        start_slots_game(user_id)

def play_slots(user_id, bet_amount):
    user_balance = get_user_balance(user_id)
    bot_liquidity = get_bot_liquidity()

    if bet_amount > user_balance:
        send_message_safely(user_id, "رصيدك غير كافٍ للعب بهذا المبلغ.")
        return

    symbols = ['🍒', '🍋', '🍊', '🍉', '🍇', '💎']
    result = [random.choice(symbols) for _ in range(3)]

    is_winner = len(set(result)) == 1  # All symbols are the same

    if is_winner and bet_amount * 2 > bot_liquidity:
        is_winner = False  # Force a loss if bot doesn't have enough liquidity

    if is_winner:
        winnings = bet_amount * 2
        new_user_balance = user_balance + winnings - bet_amount
        new_bot_liquidity = bot_liquidity - winnings + bet_amount

        update_user_balance(user_id, new_user_balance)
        update_bot_liquidity(-winnings + bet_amount)

        transaction_id = log_transaction(user_id, 'slots_win', winnings - bet_amount)
        message = (
            f"🎰 نتيجة اللعبة: {''.join(result)}\n"
            f"🎉 مبروك! لقد ربحت في لعبة Slots!\n"
            f"💰 المبلغ: ${winnings:.2f}\n"
            f"💳 رصيدك الجديد: ${new_user_balance:.2f}\n"
            f"🆔 رقم العملية: `{transaction_id}`"
        )
    else:
        new_user_balance = user_balance - bet_amount
        new_bot_liquidity = bot_liquidity + bet_amount

        update_user_balance(user_id, new_user_balance)
        update_bot_liquidity(bet_amount)

        transaction_id = log_transaction(user_id, 'slots_loss', -bet_amount)
        message = (
            f"🎰 نتيجة اللعبة: {''.join(result)}\n"
            f"😢 للأسف، لم تربح هذه المرة في لعبة Slots.\n"
            f"💸 خسرت: ${bet_amount:.2f}\n"
            f"💳 رصيدك الجديد: ${new_user_balance:.2f}\n"
            f"🆔 رقم العملية: `{transaction_id}`"
        )

    send_message_safely(user_id, message, parse_mode='Markdown')
    
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("نعم", callback_data="play_slots_again"),
                 InlineKeyboardButton("لا", callback_data="end_slots"))
    send_message_safely(user_id, "هل تريد اللعب مرة أخرى؟", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data in ["play_slots_again", "end_slots"])
def slots_callback(call):
    user_id = call.from_user.id
    if call.data == "play_slots_again":
        start_slots_game(user_id)
    else:
        send_message_safely(user_id, "شكرًا للعب! يمكنك العودة إلى القائمة الرئيسية.", reply_markup=get_main_keyboard())
    bot.answer_callback_query(call.id)

def show_loan_options(user_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("$5", callback_data="loan_5"),
                 InlineKeyboardButton("$25", callback_data="loan_25"),
                 InlineKeyboardButton("$100", callback_data="loan_100"))
    send_message_safely(user_id, "اختر مبلغ القرض:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("loan_"))
def loan_callback(call):
    user_id = call.from_user.id
    loan_amount = int(call.data.split("_")[1])
    process_loan_request(user_id, loan_amount)
    bot.answer_callback_query(call.id)

def process_loan_request(user_id, loan_amount):
    user_balance = get_user_balance(user_id)
    if user_balance >= loan_amount * 0.9:
        interest = loan_amount * 0.25
        total_to_repay = loan_amount + interest
        
        update_user_balance(user_id, user_balance + loan_amount)
        log_transaction(user_id, 'loan', loan_amount)
        
        loan_id = generate_transaction_id(user_id)
        loans_collection.insert_one({
            'loan_id': loan_id,
            'user_id': user_id,
            'amount': loan_amount,
            'interest': interest,
            'total_to_repay': total_to_repay,
            'paid': False,
            'timestamp': get_current_time()
        })
        
        message = (
            f"✅ تمت الموافقة على القرض الخاص بك!\n"
            f"💰 مبلغ القرض: ${loan_amount:.2f}\n"
            f"💸 الفائدة: ${interest:.2f}\n"
            f"🔄 المبلغ الإجمالي للسداد: ${total_to_repay:.2f}\n"
            f"🆔 رقم القرض: `{loan_id}`"
        )
        send_message_safely(user_id, message, parse_mode='Markdown')
    else:
        send_message_safely(user_id, "عذرًا، رصيدك غير كافٍ للحصول على هذا القرض. يجب أن يكون لديك 90% على الأقل من مبلغ القرض.")

def get_user_loans(user_id):
    return list(loans_collection.find({'user_id': user_id, 'paid': False}))

@bot.message_handler(func=lambda message: message.text == 'قروضي')
def my_loans(message):
    user_id = message.from_user.id
    loans = get_user_loans(user_id)
    if not loans:
        send_message_safely(user_id, "ليس لديك قروض حالية.")
        return
    
    for loan in loans:
        message = (
            f"🆔 رقم القرض: `{loan['loan_id']}`\n"
            f"💰 مبلغ القرض: ${loan['amount']:.2f}\n"
            f"💸 الفائدة: ${loan['interest']:.2f}\n"
            f"🔄 المبلغ الإجمالي للسداد: ${loan['total_to_repay']:.2f}\n"
            f"📅 تاريخ القرض: {loan['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
        )
        keyboard = InlineKeyboardMarkup()
        keyboard.row(InlineKeyboardButton("سداد القرض", callback_data=f"repay_loan_{loan['loan_id']}"))
        send_message_safely(user_id, message, reply_markup=keyboard, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith("repay_loan_"))
def repay_loan_callback(call):
    user_id = call.from_user.id
    loan_id = call.data.split("_")[2]
    repay_loan(user_id, loan_id)
    bot.answer_callback_query(call.id)

def repay_loan(user_id, loan_id):
    loan = loans_collection.find_one({'loan_id': loan_id, 'user_id': user_id, 'paid': False})
    if not loan:
        send_message_safely(user_id, "عذرًا، لم يتم العثور على القرض المحدد.")
        return
    
    user_balance = get_user_balance(user_id)
    if user_balance < loan['total_to_repay']:
        send_message_safely(user_id, "عذرًا، رصيدك غير كافٍ لسداد هذا القرض.")
        return
    
    update_user_balance(user_id, user_balance - loan['total_to_repay'])
    loans_collection.update_one({'loan_id': loan_id}, {'$set': {'paid': True}})
    log_transaction(user_id, 'loan_repayment', -loan['total_to_repay'])
    
    message = (
        f"✅ تم سداد القرض بنجاح!\n"
        f"💰 المبلغ المسدد: ${loan['total_to_repay']:.2f}\n"
        f"💳 رصيدك الجديد: ${(user_balance - loan['total_to_repay']):.2f}"
    )
    send_message_safely(user_id, message)

@bot.callback_query_handler(func=lambda call: call.data == "check_status")
def status_callback(call):
    check_status(call.from_user.id)
    bot.answer_callback_query(call.id)

def check_status(user_id):
    telegram_start_time = time.time()
    requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe")
    telegram_latency = (time.time() - telegram_start_time) * 1000

    mongo_start_time = time.time()
    client.admin.command('ping')
    mongo_latency = (time.time() - mongo_start_time) * 1000

    status_message = (
        f"📊 حالة النظام:\n\n"
        f"🚀 تأخير Telegram API: {telegram_latency:.2f} مللي ثانية\n"
        f"🗄️ تأخير قاعدة البيانات: {mongo_latency:.2f} مللي ثانية\n"
        f"⏰ الوقت الحالي (بغداد): {get_current_time().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⌛ وقت التشغيل: {get_uptime()}"
    )

    send_message_safely(user_id, status_message)

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
