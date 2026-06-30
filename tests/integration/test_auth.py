"""Testes de integração para autenticação (PocketBase mockado com responses)."""
import pytest
import responses as rsps_lib

from app import create_app

PB = "http://pb.test"

LOGIN_RESP_ALUNO = {
    "token": "tok-abc123",
    "record": {"id": "aluno01", "name": "Lucas Batista", "email": "lucas@test.com", "role": "aluno"},
}

LOGIN_RESP_PROF = {
    "token": "tok-prof",
    "record": {"id": "prof01", "name": "Prof. Ana", "email": "ana@test.com", "role": "professor"},
}

# keep old name as alias for existing tests
LOGIN_RESP = LOGIN_RESP_ALUNO


@pytest.fixture()
def app_auth():
    """App com LOGIN_REQUIRED=True para testar redirecionamentos de auth."""
    return create_app({
        "TESTING": True,
        "PB_URL": PB,
        "SECRET_KEY": "test-secret",
        "LOGIN_REQUIRED": True,
    })


@pytest.fixture()
def client_auth(app_auth):
    return app_auth.test_client()


def test_login_get_retorna_formulario(client_auth):
    resp = client_auth.get("/login")
    assert resp.status_code == 200
    assert b"Entrar" in resp.data


@rsps_lib.activate
def test_login_valido_redireciona_home(client_auth):
    rsps_lib.add(
        rsps_lib.POST,
        f"{PB}/api/collections/users/auth-with-password",
        json=LOGIN_RESP,
    )
    resp = client_auth.post("/login", data={"email": "lucas@test.com", "senha": "senha123"})
    assert resp.status_code == 302
    assert resp.headers["Location"].rstrip("/").endswith("")  # redireciona para /


@rsps_lib.activate
def test_login_invalido_retorna_401(client_auth):
    rsps_lib.add(
        rsps_lib.POST,
        f"{PB}/api/collections/users/auth-with-password",
        status=400,
        json={"code": 400, "message": "Failed to authenticate."},
    )
    resp = client_auth.post("/login", data={"email": "errado@test.com", "senha": "errada"})
    assert resp.status_code == 401
    assert "Email ou senha incorretos" in resp.data.decode()


def test_logout_limpa_sessao(client_auth):
    with client_auth.session_transaction() as sess:
        sess["token"] = "tok-abc123"
        sess["aluno_id"] = "aluno01"
        sess["aluno_nome"] = "Lucas Batista"
    resp = client_auth.get("/logout")
    assert resp.status_code == 302
    with client_auth.session_transaction() as sess:
        assert "token" not in sess
        assert "aluno_id" not in sess


def test_rota_protegida_sem_login_redireciona(client_auth):
    resp = client_auth.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_rota_protegida_com_login_passa(client_auth):
    with client_auth.session_transaction() as sess:
        sess["token"] = "tok-abc123"
        sess["aluno_nome"] = "Lucas"
    # /health não requer login — testa que a sessão não interfere
    resp = client_auth.get("/health")
    assert resp.status_code == 200


@rsps_lib.activate
def test_login_aluno_redireciona_para_home(client_auth):
    rsps_lib.add(
        rsps_lib.POST,
        f"{PB}/api/collections/users/auth-with-password",
        json=LOGIN_RESP_ALUNO,
    )
    resp = client_auth.post("/login", data={"email": "lucas@test.com", "senha": "senha123"})
    assert resp.status_code == 302
    loc = resp.headers["Location"]
    assert loc.rstrip("/").endswith("") or loc == "/"
    assert "/professor" not in loc


@rsps_lib.activate
def test_login_professor_redireciona_para_dashboard(client_auth):
    rsps_lib.add(
        rsps_lib.POST,
        f"{PB}/api/collections/users/auth-with-password",
        json=LOGIN_RESP_PROF,
    )
    resp = client_auth.post("/login", data={"email": "ana@test.com", "senha": "senha123"})
    assert resp.status_code == 302
    assert "/professor/dashboard" in resp.headers["Location"]
