import sqlalchemy as sa

from bot.main import migrate
from bot.models import Base


def test_migrations_match_models(tmp_path):
    db = tmp_path / "t.db"
    migrate(f"sqlite+aiosqlite:///{db}")
    insp = sa.inspect(sa.create_engine(f"sqlite:///{db}"))
    for table in Base.metadata.sorted_tables:
        migrated = {c["name"] for c in insp.get_columns(table.name)}
        assert migrated == {c.name for c in table.columns}, table.name
