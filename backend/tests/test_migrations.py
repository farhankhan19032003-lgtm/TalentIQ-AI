import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

BACKEND = Path(__file__).resolve().parents[1]


def _alembic(db, *args):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}"}
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120)


def test_migration_upgrade_matches_models_and_downgrades(tmp_path):
    db = tmp_path / "m.db"
    assert _alembic(db, "upgrade", "head").returncode == 0
    tables = set(sa.inspect(sa.create_engine(f"sqlite:///{db}")).get_table_names())
    assert {"jobs", "candidates", "resumes", "match_results", "evidence_items", "manual_overrides", "audit_logs"} <= tables
    chk = _alembic(db, "check")
    assert chk.returncode == 0, chk.stdout + chk.stderr          # models and migration are in sync
    assert _alembic(db, "downgrade", "base").returncode == 0
