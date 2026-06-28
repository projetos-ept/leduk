import json
import os
import pytest
from app import create_app

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture()
def app():
    return create_app({
        "TESTING": True,
        "PB_URL": "http://pb.test",
        "SECRET_KEY": "test-secret",
        "LOGIN_REQUIRED": False,
    })


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def questao_mc4():
    with open(os.path.join(FIXTURES, "questao_mc4.json")) as f:
        return json.load(f)


@pytest.fixture()
def questao_vf():
    with open(os.path.join(FIXTURES, "questao_vf.json")) as f:
        return json.load(f)


@pytest.fixture()
def questao_associativa():
    with open(os.path.join(FIXTURES, "questao_associativa.json")) as f:
        return json.load(f)
