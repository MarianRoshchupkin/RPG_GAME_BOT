import logging
import os
import uuid
import urllib3
import requests
import click

from datetime import datetime
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ---------------------
# Импорт наших моделей
# ---------------------
from models import (
    SessionLocal,
    RPGUser,
    Quest,
    QuestProgress,
    init_db
)

# Отключаем предупреждения по SSL (verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Загружаем переменные окружения
load_dotenv()

# ---------------
# Env-переменные
# ---------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GIGACHAT_AUTHORIZATION_KEY = os.getenv("GIGACHAT_AUTHORIZATION_KEY")
GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")

# Логгер
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------
#    Класс GigaChatAPI (можно копировать без изменений)
# -------------------------------------------------------
class GigaChatAPI:
    """
    Класс-обёртка для работы с GigaChat API:
    1) Получение/обновление токена доступа;
    2) Генерация ответа от модели (чата).
    """
    def __init__(self, authorization_key: str):
        self.authorization_key = authorization_key
        self.access_token = None
        self.token_expiry = datetime.utcnow()

    def get_access_token(self) -> str:
        if not self.access_token or datetime.utcnow() >= self.token_expiry:
            self.request_access_token()
        return self.access_token

    def request_access_token(self):
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Authorization": f"Basic {self.authorization_key}",
            "RqUID": str(uuid.uuid4())
        }
        data = {"scope": "GIGACHAT_API_PERS"}
        try:
            response = requests.post(url, headers=headers, data=data, verify=False)
            response.raise_for_status()
            token_info = response.json()
            self.access_token = token_info["access_token"]
            self.token_expiry = datetime.utcfromtimestamp(token_info["expires_at"] / 1000)
            logger.info("GigaChat access token получен/обновлён.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении токена GigaChat: {e}")
            raise

    def generate_game_step(self, system_role: str, user_message: str) -> str:
        """
        Генерируем ответ от GigaChat (5-этапные диалоги в рамках RPG-квеста).
        system_role — описание контекста (например, 'Ты — рассказчик RPG...'),
        user_message — сообщение игрока (его действия/вопрос).
        """
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.get_access_token()}",
            "Content-Type": "application/json",
            "X-Client-ID": GIGACHAT_CLIENT_ID,
            "X-Request-ID": str(uuid.uuid4()),
            "X-Session-ID": str(uuid.uuid4())
        }
        payload = {
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": system_role},
                {"role": "user", "content": user_message}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }

        try:
            response = requests.post(url, headers=headers, json=payload, verify=False)
            response.raise_for_status()
            response_data = response.json()
            return response_data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при обращении к GigaChat API: {e}")
            return "Произошла ошибка при обработке диалога GigaChat."


# Создаём экземпляр GigaChatAPI
giga_chat_api = GigaChatAPI(GIGACHAT_AUTHORIZATION_KEY)


# ---------------------
#   Утилиты
# ---------------------
def get_or_create_rpg_user(update: Update) -> RPGUser:
    """
    Возвращает RPGUser из БД по Telegram ID.
    Если пользователя нет, создаёт новую запись.

    Чтобы избежать DetachedInstanceError, после commit() делаем db.expunge(user_obj).
    Это отвязывает объект от сессии, но уже загруженные поля остаются доступными.
    """
    db = SessionLocal()
    try:
        tgid = update.effective_user.id
        username = update.effective_user.username

        user_obj = db.query(RPGUser).filter(RPGUser.telegram_id == tgid).first()
        if not user_obj:
            user_obj = RPGUser(telegram_id=tgid, username=username)
            db.add(user_obj)
            db.commit()

        # Отвязываем объект от сессии, чтобы избежать ошибок при дальнейших обращениях к полям
        db.expunge(user_obj)
        return user_obj
    except Exception as e:
        logger.error(f"Ошибка при get_or_create_rpg_user: {e}")
        return None
    finally:
        db.close()


def main_menu_keyboard():
    """
    Главное меню (ReplyKeyboard). Здесь — условные команды: создать персонажа, посмотреть квесты и т. п.
    """
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("/createcharacter"), KeyboardButton("/mycharacter")],
            [KeyboardButton("/quests"), KeyboardButton("/help")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


# ---------------------
#   Обработчики команд
# ---------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start — приветствие, отображение главного меню.
    """
    user_obj = get_or_create_rpg_user(update)
    if user_obj:
        await update.message.reply_text(
            "Добро пожаловать в наш RPG-Бот!\n"
            "Наберите /help, чтобы увидеть список доступных команд.",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "Ошибка при создании/получении пользователя. Попробуйте позже."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /help — показать список доступных команд.
    """
    text = (
        "Список команд:\n"
        "/start — Начать работу с ботом.\n"
        "/createcharacter — Создать нового RPG-персонажа.\n"
        "/mycharacter — Показать информацию о вашем персонаже.\n"
        "/quests — Показать список доступных квестов.\n"
        "/help — Показать это сообщение.\n"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def create_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /createcharacter — запускает диалог по созданию персонажа:
    - имя
    - класс (Мечник, Маг, Лучник)
    """
    user_obj = get_or_create_rpg_user(update)
    if not user_obj:
        await update.message.reply_text("Не удалось получить пользователя из БД.")
        return

    # Проверяем, не создан ли персонаж ранее (можно позволить пересоздание, если хотите).
    if user_obj.character_name and user_obj.character_class:
        await update.message.reply_text(
            f"У вас уже есть персонаж: {user_obj.character_name} ({user_obj.character_class}).",
            reply_markup=main_menu_keyboard()
        )
        return

    # Пошагово спрашиваем имя, потом класс:
    await update.message.reply_text("Введите имя вашего персонажа:")
    context.user_data["creating_character"] = True
    context.user_data["step"] = 1


# ---------------------
#   Обработчики команд
# ---------------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Универсальная функция, которая обрабатывает текст, когда не распознана команда.
    Если пользователь находится в процессе создания персонажа или в процессе квеста, здесь ловим шаги.
    """
    user_text = update.message.text
    user_obj = get_or_create_rpg_user(update)
    if not user_obj:
        return

    # Проверяем, находимся ли в процессе создания персонажа
    if context.user_data.get("creating_character"):
        step = context.user_data.get("step", 1)

        if step == 1:
            user_obj.character_name = user_text
            context.user_data["step"] = 2
            db = SessionLocal()
            try:
                db.add(user_obj)
                db.commit()
            finally:
                db.close()
            await update.message.reply_text("Отлично! Теперь введите класс вашего персонажа (Мечник, Маг или Лучник):")
            return

        elif step == 2:
            user_obj.character_class = user_text.capitalize()
            db = SessionLocal()
            try:
                db.add(user_obj)
                db.commit()
            finally:
                db.close()

            context.user_data["creating_character"] = False
            context.user_data["step"] = 0

            refreshed_user = get_or_create_rpg_user(update)
            await update.message.reply_text(
                f"Персонаж создан!\n"
                f"Имя: {refreshed_user.character_name}\n"
                f"Класс: {refreshed_user.character_class}\n"
                f"Уровень: {refreshed_user.level}, Опыт: {refreshed_user.experience}",
                reply_markup=main_menu_keyboard()
            )
            return

    # Проверяем, находимся ли в процессе квеста
    if context.user_data.get("in_quest"):
        # Обрабатываем текст для квеста
        await handle_quest_dialog(update, context)
        return

    # Если не в процессе создания персонажа и не в квесте
    await update.message.reply_text(
        "Неизвестная команда или сообщение. Введите /help, чтобы увидеть список команд."
    )


async def show_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /mycharacter — показывает данные персонажа.
    """
    user_obj = get_or_create_rpg_user(update)
    if not user_obj:
        await update.message.reply_text("Ошибка доступа к БД.")
        return

    if not user_obj.character_name or not user_obj.character_class:
        await update.message.reply_text("У вас ещё нет персонажа. Используйте /createcharacter.")
        return

    text = (
        f"Имя: {user_obj.character_name}\n"
        f"Класс: {user_obj.character_class}\n"
        f"Уровень: {user_obj.level}\n"
        f"Опыт: {user_obj.experience}\n"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

# ---------------------
#  Квесты
# ---------------------
async def list_quests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /quests — выводит список доступных пользователю квестов (по уровню),
    а также даёт кнопку "начать квест".
    """
    user_obj = get_or_create_rpg_user(update)
    if not user_obj:
        await update.message.reply_text("Ошибка при получении пользователя.")
        return

    db = SessionLocal()
    try:
        # Находим квесты, доступные по уровню и которые ещё не завершены данным пользователем
        available_quests = db.query(Quest).filter(
            Quest.required_level <= user_obj.level,
            Quest.is_active == True
        ).all()

        if not available_quests:
            await update.message.reply_text("Квесты не найдены или ваш уровень слишком низкий.")
            return

        # Для каждого квеста формируем Inline-кнопку
        keyboard = []
        for q in available_quests:
            # Проверяем, может квест уже завершён?
            progress = db.query(QuestProgress).filter(
                QuestProgress.user_id == user_obj.id,
                QuestProgress.quest_id == q.id,
                QuestProgress.is_completed == True
            ).first()
            if progress:
                continue  # Пропускаем уже выполненные квесты

            # Добавляем кнопку "Выбрать квест"
            keyboard.append([
                InlineKeyboardButton(
                    f"{q.title} (Lvl {q.required_level})",
                    callback_data=f"quest_select_{q.id}"
                )
            ])

        if not keyboard:
            await update.message.reply_text("Все доступные квесты уже завершены или недоступны.")
            return

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Доступные квесты:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка при получении списка квестов: {e}")
        await update.message.reply_text("Произошла ошибка при получении квестов.")
    finally:
        db.close()


async def quest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик нажатия на Inline-кнопку "выбрать квест".
    Показывает описание квеста и кнопку "Начать".
    """
    query = update.callback_query
    await query.answer()

    data = query.data  # Пример: "quest_select_3"
    if not data.startswith("quest_select_"):
        return

    quest_id_str = data.split("_")[-1]
    quest_id = int(quest_id_str)

    db = SessionLocal()
    try:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        if not quest:
            await query.edit_message_text("Квест не найден.")
            return

        text = (
            f"Название: {quest.title}\n"
            f"Описание: {quest.description}\n"
            f"Требуемый уровень: {quest.required_level}\n"
            f"Награда: {quest.reward_exp} опыта\n\n"
            f"Вы хотите начать квест?"
        )
        # Кнопка для старта
        keyboard = [
            [InlineKeyboardButton("Начать квест", callback_data=f"quest_start_{quest_id}")],
            [InlineKeyboardButton("Отмена", callback_data="quest_cancel")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        db.close()


async def quest_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "Начать квест" — создаём (или продолжаем) прогресс квеста и
    выдаём первый этап через GigaChat.
    """
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("quest_start_"):
        return

    quest_id = int(data.split("_")[-1])
    user_obj = get_or_create_rpg_user(update)
    if not user_obj:
        await query.edit_message_text("Ошибка при загрузке пользователя.")
        return

    db = SessionLocal()
    try:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        if not quest:
            await query.edit_message_text("Квест не найден.")
            return

        # Ищем или создаём запись прогресса
        progress = db.query(QuestProgress).filter(
            QuestProgress.user_id == user_obj.id,
            QuestProgress.quest_id == quest_id
        ).first()

        if not progress:
            progress = QuestProgress(
                user_id=user_obj.id,
                quest_id=quest_id,
                current_stage=0,
                is_completed=False
            )
            db.add(progress)
            db.commit()

        # Формируем сообщение для GigaChat
        system_role = "Ты — ведущий RPG-квеста. ..."
        user_prompt = "Игрок начинает квест..."

        reply_from_giga = giga_chat_api.generate_game_step(system_role, user_prompt)

        # Обновляем этап
        progress.current_stage = 1
        db.commit()

        # Активируем флаг квеста
        context.user_data["in_quest"] = True
        context.user_data["quest_progress"] = progress

        await query.edit_message_text(
            f"Квест '{quest.title}' начат!\n{reply_from_giga}"
        )
    except Exception as e:
        logger.error(f"Ошибка при старте квеста: {e}")
        await query.edit_message_text("Произошла ошибка при старте квеста.")
    finally:
        db.close()


async def quest_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отмена квеста при просмотре описания (просто убираем сообщение).
    """
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Вы отменили выбор квеста.")


# ----------------------------
#  Обработка ответов игрока во время квеста
# ----------------------------
async def handle_quest_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Когда пользователь пишет любой текст после начала квеста, мы предполагаем,
    что это "ответ" на текущем этапе. Получаем прогресс, отправляем сообщение в GigaChat,
    получаем реакцию от модели и двигаемся дальше.
    """
    # Сначала берём "сырой" объект пользователя (он у нас отсоединён от сессии)
    user_obj = get_or_create_rpg_user(update)
    if not user_obj:
        return  # на всякий случай выходим

    db = SessionLocal()
    try:
        # Ищем активный квест (где is_completed=False и этап < 6)
        progress = db.query(QuestProgress).filter(
            QuestProgress.user_id == user_obj.id,
            QuestProgress.is_completed == False,
            QuestProgress.current_stage < 6
        ).first()

        # Нет активного квеста — ничего не делаем
        if not progress:
            return

        quest = db.query(Quest).filter(Quest.id == progress.quest_id).first()
        if not quest:
            return

        # Сообщение пользователя
        player_message = update.message.text

        # Формируем prompt для GigaChat
        system_role = (
            "Ты — ведущий RPG-квеста. У нас максимум 5 этапов. "
            "На каждом этапе реагируй на действие игрока и продвигай сюжет. "
            "Если этап достигает 5-го — проверяй финальную цель квеста."
        )
        user_prompt = (
            f"Текущий квест: {quest.title}\n"
            f"Цель: {quest.final_result}\n"
            f"Игрок (класс {user_obj.character_class}) отвечает: {player_message}\n"
            f"Сейчас идёт этап № {progress.current_stage}. "
            f"Продолжи историю и опиши последствия. "
            f"Если это уже 5-й ответ, реши, удалось ли достичь финала."
        )

        reply_from_giga = giga_chat_api.generate_game_step(system_role, user_prompt)

        # Переходим на следующий этап
        progress.current_stage += 1

        # Проверяем, дошли ли до финала
        if progress.current_stage >= 5:
            # Квест завершается
            progress.is_completed = True

            # Получаем «живого» пользователя из БД в текущей сессии:
            db_user = db.query(RPGUser).filter(RPGUser.id == user_obj.id).one()
            db_user.experience += quest.reward_exp

            # Проверяем, не пора ли поднять уровень (если опыта >= 100, например)
            while db_user.experience >= 100:
                db_user.experience -= 100
                db_user.level += 1

            db.commit()

            # Сообщаем игроку о награде и новом уровне
            await update.message.reply_text(
                f"{reply_from_giga}\n\n"
                "Это был финальный этап квеста! "
                f"Вы получили {quest.reward_exp} опыта.\n"
                f"Ваш уровень теперь: {db_user.level}, опыт: {db_user.experience}."
            )

            # Снимаем флаг «в квесте»
            context.user_data["in_quest"] = False
            context.user_data["quest_progress"] = None

        else:
            # Просто сохраняем состояние и даём GigaChat-ответ
            db.commit()
            await update.message.reply_text(reply_from_giga)

    except Exception as e:
        logger.error(f"Ошибка handle_quest_dialog: {e}")
    finally:
        db.close()


# ---------------------
#   Инициализация
# ---------------------
def main():
    init_db()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("createcharacter", create_character))
    application.add_handler(CommandHandler("mycharacter", show_character))
    application.add_handler(CommandHandler("quests", list_quests))

    # Inline-калбэки для квестов
    application.add_handler(CallbackQueryHandler(quest_callback, pattern="^quest_select_"))
    application.add_handler(CallbackQueryHandler(quest_start_callback, pattern="^quest_start_"))
    application.add_handler(CallbackQueryHandler(quest_cancel_callback, pattern="^quest_cancel"))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling()

if __name__ == "__main__":
    main()