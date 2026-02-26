"""
Alembic environment configuration for Greenside AI.

Reads DATABASE_URL from environment to support both:
  - SQLite  (local dev, default)
  - PostgreSQL (production, via DATABASE_URL env var)
"""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# -- Alembic Config object (provides access to alembic.ini values) -----------
config = context.config

# -- Logging setup from alembic.ini -----------------------------------------
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# -- No declarative MetaData (we use raw-SQL migrations) ---------------------
target_metadata = None

# -- Resolve database URL ----------------------------------------------------
# Priority: DATABASE_URL env var > alembic.ini sqlalchemy.url
database_url = os.environ.get("DATABASE_URL")

if database_url:
    # Railway/Heroku sometimes provide postgres:// which SQLAlchemy 2.x rejects
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    config.set_main_option("sqlalchemy.url", database_url)
else:
    # Default to local SQLite — same path used by chat_history.py / db.py
    data_dir = os.environ.get("DATA_DIR", "data" if os.path.exists("data") else ".")
    sqlite_path = os.path.join(data_dir, "greenside_conversations.db")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{sqlite_path}")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emits SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite doesn't support ALTER for most operations;
            # render_as_batch lets Alembic work around that.
            render_as_batch=is_sqlite,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
