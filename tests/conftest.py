import os

import pytest

os.environ.setdefault("SWARMS_GLOBAL_LOGGER_ON", "false")


@pytest.fixture(scope="session")
def mock_settings():
    os.environ.pop("YCC_MODE", None)
    from ycc import mock_prune
    from ycc.config import load_settings
    s = load_settings()
    mock_prune.start()
    yield s
    mock_prune.stop()


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    from ycc import approval
    db = tmp_path / "test.db"
    monkeypatch.setattr(approval, "DB", db)
    return db
