import os, sys, tempfile
_tmp = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(_tmp, "teste.db")      # antes de importar o db.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

@pytest.fixture(scope="session")
def mundo():
    from app.data import db
    db.ExData()                      # 3 veículos de exemplo
    from app.app import app, GarantirQRs
    GarantirQRs()
    app.testing = True
    return app.test_client()
