import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect("cloakroom.db")
    cursor = conn.cursor()

    # Создание таблиц, если они не существуют
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hangers (
        id INTEGER PRIMARY KEY,
        status TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        hanger_id INTEGER
    )
    """)

    # Заполнение номеров гардеробов, если таблица пуста
    cursor.execute("SELECT COUNT(*) FROM hangers")
    if cursor.fetchone()[0] == 0:
        for i in range(1, 201):  # Номера от 1 до 200
            cursor.execute("INSERT INTO hangers (id, status) VALUES (?, 'free')", (i,))
        conn.commit()

    conn.close()

# Функция для отображения кнопок
async def show_buttons(update: Update, user_id: int, delete_prev_msg=False) -> None:
    keyboard = [
        [InlineKeyboardButton("Взять номерок", callback_data='get_hanger')]
    ]

    # Подключаемся к базе данных
    conn = sqlite3.connect("cloakroom.db")
    cursor = conn.cursor()
    cursor.execute("SELECT hanger_id FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if user:
        keyboard = [
            [InlineKeyboardButton("Сдать номерок", callback_data='free_hanger')]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Удаление предыдущего сообщения, если задано
    if delete_prev_msg and update.callback_query:
        await update.callback_query.message.delete()

    # Отправляем новое сообщение с кнопками
    if update.message:
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text("Выберите действие:", reply_markup=reply_markup)

    conn.close()

# Команда для начала работы с ботом
async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    await update.message.reply_text(
        "Добро пожаловать в бота гардеробщика, здесь вы можете получить электронный номерок"
    )
    await show_buttons(update, user_id)

# Команда для получения номерка
async def get_hanger(update: Update, context: CallbackContext) -> None:
    conn = sqlite3.connect("cloakroom.db")
    cursor = conn.cursor()

    user_id = update.callback_query.from_user.id
    cursor.execute("SELECT hanger_id FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if user:
        await update.callback_query.message.reply_text(
            f"Вы уже взяли номерок {user[0]}. Чтобы его сдать, нажмите кнопку."
        )
        await show_buttons(update, user_id)
        conn.close()
        return

    # Ищем первый свободный номерок
    cursor.execute("SELECT id FROM hangers WHERE status = 'free' ORDER BY id LIMIT 1")
    row = cursor.fetchone()

    if row:
        hanger_id = row[0]
        cursor.execute("UPDATE hangers SET status = 'taken' WHERE id = ?", (hanger_id,))
        cursor.execute("INSERT INTO users (user_id, hanger_id) VALUES (?, ?)", (user_id, hanger_id))
        conn.commit()

        # Сообщение с номерком
        await update.callback_query.message.reply_text(f"Ваш номерок № {hanger_id}")
        # Удаление предыдущего и новое сообщение с кнопкой "Сдать номерок"
        await show_buttons(update, user_id, delete_prev_msg=True)
    else:
        await update.callback_query.message.reply_text("К сожалению, все номерки заняты.")

    conn.close()

# Команда для освобождения номерка
async def free_hanger(update: Update, context: CallbackContext) -> None:
    conn = sqlite3.connect("cloakroom.db")
    cursor = conn.cursor()
    user_id = update.callback_query.from_user.id

    cursor.execute("SELECT hanger_id FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        await update.callback_query.message.reply_text("Вы не брали номерок.")
        conn.close()
        return

    hanger_id = user[0]
    cursor.execute("UPDATE hangers SET status = 'free' WHERE id = ?", (hanger_id,))
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()

    await update.callback_query.message.reply_text("Вы успешно сдали номерок!")
    await show_buttons(update, user_id, delete_prev_msg=True)

    conn.close()

# Обработка нажатия кнопок
async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    action = query.data

    if action == 'get_hanger':
        await get_hanger(update, context)
    elif action == 'free_hanger':
        await free_hanger(update, context)

    await query.answer()

# Настройка команд бота
def main():
    init_db()

    application = Application.builder().token("YOUR_BOT_TOKEN").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()

if __name__ == '__main__':
    main()
