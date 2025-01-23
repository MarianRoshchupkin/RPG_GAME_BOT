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
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)  # Краткое описание
    required_level = Column(Integer, default=1)        # С какого уровня квест доступен
    reward_exp = Column(Integer, default=0)            # Сколько опыта даёт за выполнение
    final_result = Column(String(500), nullable=False) # Критерий "что нужно сделать" (логический финал)

    # Например, флаг "активный/неактивный" или другие поля
    is_active = Column(Boolean, default=True)


class QuestProgress(Base):
    """
    Таблица 'quest_progress' для хранения состояния квеста у конкретного пользователя.
    """
    __tablename__ = "quest_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("rpg_users.id"), nullable=False)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False)
    current_stage = Column(Integer, default=0)     # Какой этап квеста сейчас
    is_completed = Column(Boolean, default=False)  # Завершён ли квест

    user = relationship("RPGUser", back_populates="quest_progresses")

# ---------- Настройка базы данных ----------
engine = create_engine("sqlite:///rpg_db.sqlite3", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Создаёт таблицы в базе, если их нет.
    """
    Base.metadata.create_all(bind=engine)