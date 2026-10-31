"""Run Alembic migrations programmatically (used at startup and by `python -m app.migrate`)."""
from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import get_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().sqlalchemy_url.replace("%", "%%"))
    return cfg


def upgrade_head() -> None:
    command.upgrade(alembic_config(), "head")


if __name__ == "__main__":
    upgrade_head()
    print("Database migrated to head")
