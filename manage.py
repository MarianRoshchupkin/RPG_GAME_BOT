import click
import sys
import subprocess
from dotenv import load_dotenv

from models import init_db, Base, engine

load_dotenv()

@click.group()
def cli():
    pass

@cli.command()
def initdb():
    """
    Создаёт таблицы в базе данных (если ещё не созданы).
    """
    click.echo("Инициализация базы данных...")
    try:
        init_db()
        click.echo("Таблицы успешно созданы!")
    except Exception as e:
        click.echo(f"Ошибка при создании таблиц: {e}")

@cli.command()
def runbot():
    """
    Запуск Telegram-бота (скрипт bot.py).
    """
    click.echo("Запускаем RPG-бот...")
    try:
        subprocess.run([sys.executable, "bot.py"], check=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"Ошибка при запуске бота: {e}")

@cli.command()
def resetdb():
    """
    Полный сброс БД (DROP ALL), затем повторная инициализация.
    Требует подтверждения.
    """
    confirm = click.prompt(
        "Вы уверены, что хотите УДАЛИТЬ все таблицы? (yes/no)",
        default="no"
    )
    if confirm.lower() == "yes":
        click.echo("Удаляем все таблицы...")
        try:
            Base.metadata.drop_all(engine)
            click.echo("Таблицы удалены.")
            init_db()
            click.echo("База данных создана заново.")
        except Exception as e:
            click.echo(f"Ошибка сброса БД: {e}")
    else:
        click.echo("Сброс БД отменён.")

if __name__ == "__main__":
    cli()