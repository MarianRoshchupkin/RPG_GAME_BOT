from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    ForeignKey,
    DateTime,
    text,
    create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import sys

Base = declarative_base()

class RPGUser(Base):
    """
    Таблица 'rpg_users' для хранения информации о пользователях и их RPG-персонаже.
    """
    __tablename__ = "rpg_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255), nullable=True)

    # Данные RPG-персонажа
    character_name = Column(String(255), nullable=True)
    character_class = Column(String(50), nullable=True)
    level = Column(Integer, default=1)
    experience = Column(Integer, default=0)

    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP")
    )

    # Связь с таблицей прогресса квестов: один пользователь — много записей о квестах
    quest_progresses = relationship("QuestProgress", back_populates="user", cascade="all, delete-orphan")


class Quest(Base):
    """
    Таблица 'quests' для хранения списка доступных квестов (мастер-список).
    """
    __tablename__ = "quests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False, unique=True)  # Сделаем название уникальным для предотвращения дублей
    description = Column(String(1000), nullable=True)  # Краткое описание
    required_level = Column(Integer, default=1)  # С какого уровня квест доступен
    reward_exp = Column(Integer, default=0)  # Сколько опыта даёт за выполнение
    final_result = Column(String(500), nullable=False)  # Критерий "что нужно сделать" (логический финал)

    # Например, флаг "активный/неактивный" или другие поля
    is_active = Column(Boolean, default=True)

    # Если требуется, можно добавить связь с прогрессом квестов
    quest_progresses = relationship("QuestProgress", back_populates="quest", cascade="all, delete-orphan")


class QuestProgress(Base):
    """
    Таблица 'quest_progress' для хранения состояния квеста у конкретного пользователя.
    """
    __tablename__ = "quest_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("rpg_users.id"), nullable=False)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False)
    current_stage = Column(Integer, default=0)  # Какой этап квеста сейчас
    is_completed = Column(Boolean, default=False)  # Завершён ли квест

    user = relationship("RPGUser", back_populates="quest_progresses")
    quest = relationship("Quest", back_populates="quest_progresses")


# ---------- Настройка базы данных ----------
DATABASE_URL = "sqlite:///rpg_db.sqlite3"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    Создаёт таблицы в базе, если их нет.
    """
    Base.metadata.create_all(bind=engine)
    print("Таблицы успешно созданы или уже существуют.")


def populate_quests():
    """
    Заполняет таблицу 'quests' данными о квестах.
    """
    # Создаём сессию
    session = SessionLocal()

    # Список квестов для добавления
    quests = [
        {
            "title": "Пути-распутья",
            "description": "Игрок прибывает в маленькую деревню, знакомясь с местной фауной. Жители деревни страдают от нападений волков.",
            "final_result": "Найти старосту, выслушать жалобы жителей и согласиться помочь.",
            "required_level": 1,
            "reward_exp": 25
        },
        {
            "title": "Серые тени в лесу",
            "description": "Жители утверждают, что волки стали агрессивными из-за 'тени в лесу'. Игрок должен исследовать лес.",
            "final_result": "Найти логово волков, убить их вожака.",
            "required_level": 1,
            "reward_exp": 50
        },
        {
            "title": "Таинственные руны",
            "description": "Во время исследования игрок находит камень с непонятными рунами. Местный знахарь может помочь расшифровать их.",
            "final_result": "Доставить камень знахарю.",
            "required_level": 1,
            "reward_exp": 25
        },
        {
            "title": "Пропавший караван",
            "description": "Торговый караван пропал по дороге в соседнюю деревню. Игроку нужно узнать, что с ним произошло.",
            "final_result": "Найти караван, защитить оставшихся выживших от бандитов.",
            "required_level": 2,
            "reward_exp": 50
        },
        {
            "title": "Призрак мельника",
            "description": "Старую мельницу окутали слухи о призраке, пугающем путников.",
            "final_result": "Изгнать призрака с помощью найденного артефакта.",
            "required_level": 2,
            "reward_exp": 50
        },
        {
            "title": "Клинок из прошлого",
            "description": "Охотник находит ржавый меч в лесу. Местные уверены, что это часть старого проклятия.",
            "final_result": "Найти кузнеца, восстановить меч и узнать его историю.",
            "required_level": 3,
            "reward_exp": 10
        },
        {
            "title": "Кладбище под луной",
            "description": "Игрока отправляют на старое кладбище, где по ночам слышны странные звуки.",
            "final_result": "Выследить и уничтожить гуля или другую нежить.",
            "required_level": 3,
            "reward_exp": 35
        },
        {
            "title": "Пленники болот",
            "description": "Группа крестьян пропала на болотах. Игроку предстоит отыскать их и выяснить причину их исчезновения.",
            "final_result": "Освободить пленников от утопцев.",
            "required_level": 3,
            "reward_exp": 55
        },
        {
            "title": "Воровская тропа",
            "description": "В деревне зачастили кражи, жители подозревают соседний лагерь бандитов.",
            "final_result": "Ликвидировать лагерь бандитов.",
            "required_level": 4,
            "reward_exp": 50
        },
        {
            "title": "Охота на грифона",
            "description": "Над деревнями начал кружить грифон, нападая на скот.",
            "final_result": "Убить грифона, собрать его перья как доказательство.",
            "required_level": 4,
            "reward_exp": 50
        },
        {
            "title": "Загадочный алхимик",
            "description": "Алхимик из города ищет помощника для создания мощного зелья.",
            "final_result": "Собрать ингредиенты и помочь алхимику завершить работу.",
            "required_level": 5,
            "reward_exp": 100
        },
        {
            "title": "Проклятая башня",
            "description": "Башня, окруженная магическим барьером, начала излучать странный свет.",
            "final_result": "Войти в башню, обезвредить источник магии.",
            "required_level": 6,
            "reward_exp": 100
        },
        {
            "title": "Танец с огнём",
            "description": "Игроку нужно пробраться в логово саламандр, которые нападают на близлежащие деревни.",
            "final_result": "Уничтожить главного саламандра.",
            "required_level": 7,
            "reward_exp": 100
        },
        {
            "title": "Гибельное проклятие",
            "description": "В деревне начала распространяться неизвестная болезнь.",
            "final_result": "Найти причину болезни и избавить жителей от проклятия.",
            "required_level": 7,
            "reward_exp": 100
        },
        {
            "title": "Враг в темноте",
            "description": "Игрок должен спуститься в шахты, где скрывается жуткое существо.",
            "final_result": "Уничтожить чудовище и вернуть шахтёрам их рабочее место.",
            "required_level": 9,
            "reward_exp": 100
        },
        {
            "title": "Древний враг",
            "description": "Страж древнего леса ожил и нападает на путников.",
            "final_result": "Сразить стража, при этом сохранив баланс леса.",
            "required_level": 10,
            "reward_exp": 100
        },
        {
            "title": "Мятеж на границе",
            "description": "Игроку поручают разобраться с мятежом на границе двух королевств.",
            "final_result": "Ликвидировать мятеж или договориться о перемирии.",
            "required_level": 10,
            "reward_exp": 100
        },
        {
            "title": "Последний контракт",
            "description": "Барон просит игрока уничтожить чудище, терроризирующее округу.",
            "final_result": "Убить легендарного монстра.",
            "required_level": 12,
            "reward_exp": 500
        },
        {
            "title": "Судьба мира",
            "description": "Игрок обнаруживает, что древний артефакт, спрятанный в руинах, может уничтожить мир.",
            "final_result": "Защитить артефакт или уничтожить его.",
            "required_level": 15,
            "reward_exp": 1000
        },
        {
            "title": "Последний бой",
            "description": "Главный антагонист игры, тёмный маг, вызывает игрока на дуэль.",
            "final_result": "Победить мага, предотвратив катастрофу. Возможность начать игру заново с создания персонажа.",
            "required_level": 15,
            "reward_exp": 1200
        },
    ]

    try:
        for quest_data in quests:
            # Проверяем, существует ли уже квест с таким названием
            existing_quest = session.query(Quest).filter_by(title=quest_data["title"]).first()
            if not existing_quest:
                quest = Quest(
                    title=quest_data["title"],
                    description=quest_data["description"],
                    final_result=quest_data["final_result"],
                    required_level=quest_data["required_level"],
                    reward_exp=quest_data["reward_exp"],
                    is_active=True  # По умолчанию активный
                )
                session.add(quest)
                print(f"Добавлен квест: {quest.title}")
            else:
                print(f"Квест уже существует: {existing_quest.title}")

        # Фиксируем изменения в базе данных
        session.commit()
        print("Все квесты успешно добавлены.")

    except Exception as e:
        session.rollback()
        print(f"Произошла ошибка при добавлении квестов: {e}", file=sys.stderr)

    finally:
        session.close()


def main():
    """
    Основная функция для инициализации базы данных и заполнения квестами.
    """
    init_db()
    populate_quests()


if __name__ == "__main__":
    main()