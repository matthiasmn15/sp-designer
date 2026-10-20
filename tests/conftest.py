import pytest
from fastapi.testclient import TestClient

from sp_designer.api import create_app
from sp_designer.materials.database import MaterialDatabase
from sp_designer.prices.store import PriceStore


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path


@pytest.fixture
def prices(data_dir):
    return PriceStore(data_dir)


@pytest.fixture
def db(data_dir, prices):
    return MaterialDatabase(data_dir, prices)


@pytest.fixture
def client(data_dir):
    return TestClient(create_app(data_dir))
