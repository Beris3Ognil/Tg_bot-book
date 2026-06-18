import sqlite3
import telebot
import os 
from dotenv import load_dotenv
from telebot import types

load_dotenv()

TOKEN = os.getenv("KEY")
bot = telebot.TeleBot(TOKEN)

CHIEF_ADMIN_ID = 2135773286

user_data = {}
active_sessions = {}

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            genre TEXT,
            status TEXT NOT NULL,
            rating TEXT DEFAULT 'Нет оценки',
            description TEXT DEFAULT 'Без описания'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            tg_user_id INTEGER,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def execute_query(query, params=(), fetch=False):
    try:
        conn = sqlite3.connect('library.db')
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch:
            result = cursor.fetchall()
        else:
            conn.commit()
            result = None
        conn.close()
        return result
    except Exception as e:
        print(f"Ошибка БД: {e}")
        return []

def main_menu(tg_user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    if tg_user_id in active_sessions:
        markup.row('➕ Добавить книгу', '📚 Мои книги')
        markup.row('🔍 Поиск книг', '🚪 Выйти из аккаунта')
    else:
        markup.row('🔑 Войти', '📝 Зарегистрироваться')
        
    is_db_admin = False
    if tg_user_id in active_sessions:
        res = execute_query("SELECT is_admin FROM users WHERE username = ?", (active_sessions[tg_user_id],), fetch=True)
        if res and res[0][0] == 1:
            is_db_admin = True
            
    if tg_user_id == CHIEF_ADMIN_ID or is_db_admin:
        markup.row('👑 АДМИН ПАНЕЛЬ')
        
    return markup

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    tg_user_id = message.from_user.id
    
    if tg_user_id in active_sessions:
        bot.send_message(message.chat.id, f" Ты авторизован как: **{active_sessions[tg_user_id]}**", reply_markup=main_menu(tg_user_id), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "Добро пожаловать! Пожалуйста, войдите в аккаунт или зарегистрируйтесь.", reply_markup=main_menu(tg_user_id))

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    tg_user_id = message.from_user.id
    
    if message.text in ['🔑 Войти', '📝 Зарегистрироваться', '➕ Добавить книгу', '📚 Мои книги', '🔍 Поиск книг', '🚪 Выйти из аккаунта', '👑 АДМИН ПАНЕЛЬ']:
        bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)

    if message.text == '📝 Зарегистрироваться':
        msg = bot.send_message(message.chat.id, "Придумай уникальный никнейм (логин) для входа:")
        bot.register_next_step_handler(msg, reg_username)
        
    elif message.text == '🔑 Войти':
        msg = bot.send_message(message.chat.id, " Введи свой никнейм (логин):")
        bot.register_next_step_handler(msg, login_username)
        
    elif message.text == '🚪 Выйти из аккаунта':
        active_sessions.pop(tg_user_id, None)
        bot.send_message(message.chat.id, "Вы вышли из аккаунта.", reply_markup=main_menu(tg_user_id))

    elif message.text == '➕ Добавить книгу':
        if tg_user_id not in active_sessions:
            bot.send_message(message.chat.id, "❌ Сначала войдите в аккаунт!")
            return
        msg = bot.send_message(message.chat.id, "📝 Введите НАЗВАНИЕ книги:")
        bot.register_next_step_handler(msg, process_title)
        
    elif message.text == '📚 Мои книги':
        if tg_user_id not in active_sessions: return
        username = active_sessions[tg_user_id]
        books = execute_query("SELECT id, title, status, rating FROM books WHERE username = ?", (username,), fetch=True)
        if not books:
            bot.send_message(message.chat.id, "Твоя библиотека пока пуста.")
            return
        
        markup = types.InlineKeyboardMarkup()
        for book_id, title, status, rating in books:
            markup.add(types.InlineKeyboardButton(f"📖 {title} | {status} [{rating}]", callback_data=f"manage_{book_id}"))
        bot.send_message(message.chat.id, "Твои книги:", reply_markup=markup)
        
    elif message.text == '🔍 Поиск книг':
        if tg_user_id not in active_sessions: return
        msg = bot.send_message(message.chat.id, "🔍 Введи название или автора:")
        bot.register_next_step_handler(msg, process_search)
        
    elif message.text == '👑 АДМИН ПАНЕЛЬ':
        is_db_admin = False
        if tg_user_id in active_sessions:
            res = execute_query("SELECT is_admin FROM users WHERE username = ?", (active_sessions[tg_user_id],), fetch=True)
            if res and res[0][0] == 1:
                is_db_admin = True
                
        if tg_user_id != CHIEF_ADMIN_ID and not is_db_admin:
            bot.send_message(message.chat.id, "У вас нет прав доступа.")
            return
            
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("👀 Смотреть ВСЕ книги в БД", callback_data="admin_view_books"))
        markup.row(types.InlineKeyboardButton("⭐ Управление Админами", callback_data="admin_manage_rights"))
        bot.send_message(message.chat.id, "⚙️ Меню Администратора:", reply_markup=markup)

def reg_username(message):
    if message.text in ['🔑 Войти', '📝 Зарегистрироваться']: return
    username = message.text.strip()
    
    res = execute_query("SELECT * FROM users WHERE username = ?", (username,), fetch=True)
    if res:
        msg = bot.send_message(message.chat.id, "❌ Этот ник уже занят! Придумай другой:")
        bot.register_next_step_handler(msg, reg_username)
        return
        
    user_data[message.from_user.id] = {'reg_user': username}
    msg = bot.send_message(message.chat.id, f"🔑 Отлично, ник '{username}' свободен.\n\nТеперь придумай ПАРОЛЬ:")
    bot.register_next_step_handler(msg, reg_password)

def reg_password(message):
    tg_user_id = message.from_user.id
    if tg_user_id not in user_data: return
    password = message.text.strip()
    username = user_data[tg_user_id]['reg_user']
    
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    
    is_admin = 1 if tg_user_id == CHIEF_ADMIN_ID else 0
    
    execute_query("INSERT INTO users (username, password, tg_user_id, is_admin) VALUES (?, ?, ?, ?)", 
                  (username, password, tg_user_id, is_admin))
    
    bot.send_message(message.chat.id, f"🔒 Пароль принят: `****` \n\n🎉 Регистрация успешна! Нажми '🔑 Войти', чтобы зайти в аккаунт.", parse_mode="Markdown")
    user_data.pop(tg_user_id, None)

def login_username(message):
    if message.text in ['🔑 Войти', '📝 Зарегистрироваться']: return
    username = message.text.strip()
    
    res = execute_query("SELECT password FROM users WHERE username = ?", (username,), fetch=True)
    if not res:
        bot.send_message(message.chat.id, "❌ Пользователь с таким ником не найден.")
        return
        
    user_data[message.from_user.id] = {'login_user': username, 'correct_pass': res[0][0]}
    msg = bot.send_message(message.chat.id, f"Ник найден. Введи пароль для '{username}':")
    bot.register_next_step_handler(msg, login_password)

def login_password(message):
    tg_user_id = message.from_user.id
    if tg_user_id not in user_data: return
    password = message.text.strip()
    
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    
    if password == user_data[tg_user_id]['correct_pass']:
        username = user_data[tg_user_id]['login_user']
        active_sessions[tg_user_id] = username
        
        # Обновляем текущий Telegram ID пользователя в базе на случай, если он зашел с другого акка
        execute_query("UPDATE users SET tg_user_id = ? WHERE username = ?", (tg_user_id, username))
        
        bot.send_message(message.chat.id, f"✅ Успешный вход! Добро пожаловать, {username}.", reply_markup=main_menu(tg_user_id))
    else:
        bot.send_message(message.chat.id, "❌ Неверный пароль. Попробуй войти заново.")
    user_data.pop(tg_user_id, None)

def process_title(message):
    if message.text in ['➕ Добавить книгу', '📚 Мои книги', '🔍 Поиск книг', '👑 АДМИН ПАНЕЛЬ']: return
    user_data[message.from_user.id] = {'title': message.text}
    msg = bot.send_message(message.chat.id, "👤 Введите АВТОРА:")
    bot.register_next_step_handler(msg, process_author)

def process_author(message):
    if message.text in ['➕ Добавить книгу', '📚 Мои книги', '🔍 Поиск книг', '👑 АДМИН ПАНЕЛЬ']: return
    user_id = message.from_user.id
    if user_id not in user_data: return
    user_data[user_id]['author'] = message.text
    msg = bot.send_message(message.chat.id, "🏷️ Введите ЖАНР:")
    bot.register_next_step_handler(msg, process_genre)

def process_genre(message):
    if message.text in ['➕ Добавить книгу', '📚 Мои книги', '🔍 Поиск книг', '👑 АДМИН ПАНЕЛЬ']: return
    user_id = message.from_user.id
    if user_id not in user_data: return
    user_data[user_id]['genre'] = message.text
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⏩ Пропустить описание", callback_data="skip_description"))
    msg = bot.send_message(message.chat.id, "✍️ Введите краткое ОПИСАНИЕ:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_description)

def process_description(message):
    if message.text in ['➕ Добавить книгу', '📚 Мои книги', '🔍 Поиск книг', '👑 АДМИН ПАНЕЛЬ']: return
    user_id = message.from_user.id
    if user_id not in user_data: return
    user_data[user_id]['description'] = message.text
    show_status_selection(message.chat.id, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "skip_description")
def skip_description_callback(call):
    user_id = call.from_user.id
    if user_id not in user_data: return
    bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
    user_data[user_id]['description'] = "Без описания"
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_status_selection(call.message.chat.id, user_id)

def show_status_selection(chat_id, user_id):
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("Хочу купить", callback_data="status_хочу купить"))
    markup.row(types.InlineKeyboardButton("Читаю", callback_data="status_читаю"))
    markup.row(types.InlineKeyboardButton("Прочитано", callback_data="status_прочитано"))
    bot.send_message(chat_id, f"Выбираем статус для '{user_data[user_id]['title']}':", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('status_'))
def process_status_callback(call):
    user_id = call.from_user.id
    status = call.data.split('_')[1]
    if user_id not in user_data: return
    user_data[user_id]['status'] = status

    if status == "прочитано":
        markup = types.InlineKeyboardMarkup()
        markup.row(*[types.InlineKeyboardButton(f"⭐ {i}", callback_data=f"initrate_{i}") for i in range(1, 6)])
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Поставь оценку от 1 до 5:", reply_markup=markup)
    else:
        username = active_sessions[user_id]
        execute_query("INSERT INTO books (username, title, author, genre, status, description) VALUES (?, ?, ?, ?, ?, ?)",
                      (username, user_data[user_id]['title'], user_data[user_id]['author'], user_data[user_id]['genre'], status, user_data[user_id]['description']))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="✅ Книга сохранена!")
        user_data.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith('initrate_'))
def init_rate_callback(call):
    user_id = call.from_user.id
    rating_val = call.data.split('_')[1] + " / 5 ⭐"
    if user_id not in user_data: return
    
    username = active_sessions[user_id]
    execute_query("INSERT INTO books (username, title, author, genre, status, rating, description) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (username, user_data[user_id]['title'], user_data[user_id]['author'], user_data[user_id]['genre'], user_data[user_id]['status'], rating_val, user_data[user_id]['description']))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"✅ Книга сохранена с оценкой {rating_val}!")
    user_data.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith('manage_'))
def manage_book_callback(call):
    book_id = int(call.data.split('_')[1])
    res = execute_query("SELECT title, author, genre, status, rating, description, username FROM books WHERE id = ?", (book_id,), fetch=True)
    if not res: return
    title, author, genre, status, rating, description, owner_username = res[0]

    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("✏️ Изменить описание", callback_data=f"menu_desc_{book_id}"), types.InlineKeyboardButton("❌ Удалить книгу", callback_data=f"delete_{book_id}"))
    markup.row(types.InlineKeyboardButton("🌟 Поддержать автора (5 Звёзд)", callback_data=f"stars_donate_{book_id}"))
    
    text = (
        f"📖 **{title}**\n"
        f"👤 Автор книги: {author}\n"
        f"🔒 Владелец аккаунта: {owner_username}\n"
        f"📊 Статус: {status} | Оценка: {rating}\n"
        f"📋 Описание: _{description}_"
    )
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('stars_donate_'))
def stars_donate_callback(call):
    book_id = call.data.split('_')[2]
    res = execute_query("SELECT title FROM books WHERE id = ?", (book_id,), fetch=True)
    title = res[0][0] if res else "книгу"

    bot.send_invoice(
        chat_id=call.message.chat.id,
        title="Поддержка создателя",
        description=f"Донат за обзор книги '{title}'",
        invoice_payload=f"donate_{book_id}",
        provider_token="", 
        currency="XTR",
        prices=[types.LabeledPrice(label="Донат", amount=5)] 
    )
    bot.answer_callback_query(call.id)

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    bot.send_message(message.chat.id, "🎉 Спасибо за поддержку звездными донатами!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback(call):
    action = call.data.replace('admin_', '')
    
    if action == "view_books":
        all_books = execute_query("SELECT id, username, title, status FROM books", fetch=True)
        if not all_books:
            bot.edit_message_text("В базе данных нет книг.", call.message.chat.id, call.message.message_id)
            return
            
        markup = types.InlineKeyboardMarkup()
        for b_id, user, title, status in all_books:
            short_title = title if len(title) <= 15 else title[:12] + "..."
            markup.add(types.InlineKeyboardButton(f"👤 {user} | {short_title} ({status})", callback_data=f"manage_{b_id}"))
        bot.edit_message_text("📋 Все книги пользователей в системе:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif action == "manage_rights":
        msg = bot.send_message(call.message.chat.id, "Введите текстовый НИКНЕЙМ (логин) пользователя, которого хотите сделать админом / забрать права:")
        bot.register_next_step_handler(msg, process_toggle_admin)

def process_toggle_admin(message):
    if message.text in ['🔑 Войти', '📝 Зарегистрироваться', '➕ Добавить книгу', '📚 Мои книги', '👑 АДМИН ПАНЕЛЬ']: return
    target_username = message.text.strip()
    
    res = execute_query("SELECT is_admin FROM users WHERE username = ?", (target_username,), fetch=True)
    if not res:
        bot.send_message(message.chat.id, f"❌ Пользователь с логином '{target_username}' не зарегистрирован.")
        return
        
    current_status = res[0][0]
    new_status = 0 if current_status == 1 else 1
    execute_query("UPDATE users SET is_admin = ? WHERE username = ?", (new_status, target_username))
    
    status_text = "теперь АДМИНИСТРАТОР! 👑" if new_status == 1 else "больше не админ. ❌"
    bot.send_message(message.chat.id, f"Пользователь {target_username} {status_text}", reply_markup=main_menu(message.from_user.id))

@bot.callback_query_handler(func=lambda call: call.data.startswith('menu_desc_'))
def menu_desc_callback(call):
    book_id = int(call.data.split('_')[2])
    msg = bot.send_message(call.message.chat.id, "✍️ Введи НОВОЕ описание/отзыв:")
    bot.register_next_step_handler(msg, process_update_description, book_id)

def process_update_description(message, book_id):
    if message.text in ['➕ Добавить книгу', '📚 Мои книги', '🔍 Поиск книг', '👑 АДМИН ПАНЕЛЬ']: return
    execute_query("UPDATE books SET description = ? WHERE id = ?", (message.text, book_id))
    bot.send_message(message.chat.id, "✅ Описание успешно изменено!", reply_markup=main_menu(message.from_user.id))

def process_search(message):
    if message.text in ['➕ Добавить книгу', '📚 Мои книги', '🔍 Поиск книг', '👑 АДМИН ПАНЕЛЬ']: return
    username = active_sessions[message.from_user.id]
    found = execute_query("SELECT id, title, author, status FROM books WHERE username = ? AND (title LIKE ? OR author LIKE ?)", (username, f"%{message.text}%", f"%{message.text}%"), fetch=True)
    if not found:
        bot.send_message(message.chat.id, "Ничего не найдено.")
        return
    markup = types.InlineKeyboardMarkup()
    for b_id, title, author, status in found:
        markup.add(types.InlineKeyboardButton(f"📖 {title} ({status})", callback_data=f"manage_{b_id}"))
    bot.send_message(message.chat.id, "Результаты:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_callback(call):
    execute_query("DELETE FROM books WHERE id = ?", (int(call.data.split('_')[1]),))
    bot.edit_message_text("🗑️ Книга удалена.", call.message.chat.id, call.message.message_id)

if __name__ == '__main__':
    init_db()
    print("Бот авторизации запущен...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)