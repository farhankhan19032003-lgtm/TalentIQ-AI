from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.core.database import Base
from app.models import db  # noqa: F401  (register models)

target_metadata = Base.metadata
url = settings.database_url


def run_migrations_offline():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, render_as_batch=url.startswith("sqlite"))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=url.startswith("sqlite"))
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
