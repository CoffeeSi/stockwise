"""Apply bundled Alembic revisions without depending on a repository-root ini file."""
from pathlib import Path

from alembic import command
from alembic.config import Config


def main() -> None:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "persistence" / "migrations"))
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
