"""Redefinição de senha (público + professor) e cadastro manual de aluno."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import responses as rsps_lib

import app as app_mod

PB = "http://pb.test"


def _data(delta_horas):
    return (datetime.now(timezone.utc) + timedelta(hours=delta_horas)).strftime("%Y-%m-%d %H:%M:%S.000Z")


TOKEN_VALIDO = {"id": "tk1", "aluno_id": "al1", "token": "abc", "expira_em": _data(24), "usado": False}
TOKEN_EXPIRADO = {"id": "tk2", "aluno_id": "al1", "token": "old", "expira_em": _data(-1), "usado": False}
USER = {"id": "al1", "name": "João", "email": "joao@x.com"}


def _sess_prof(client):
    with client.session_transaction() as s:
        s["token"] = "tok"; s["role"] = "professor"; s["aluno_nome"] = "Prof"


# ── Público: /redefinir-senha/<token> ───────────────────────────────────────────

@rsps_lib.activate
def test_get_token_valido_200(client):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tokens_senha/records", json={"items": [TOKEN_VALIDO]})
    resp = client.get("/redefinir-senha/abc")
    assert resp.status_code == 200
    assert "Definir nova senha" in resp.data.decode()


@rsps_lib.activate
def test_get_token_expirado_erro(client):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tokens_senha/records", json={"items": [TOKEN_EXPIRADO]})
    resp = client.get("/redefinir-senha/old")
    assert resp.status_code == 410
    assert "não é mais válido" in resp.data.decode()


@rsps_lib.activate
def test_get_token_usado_erro(client):
    # filtro usado=false → PB não retorna; simulamos com items vazio
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tokens_senha/records", json={"items": []})
    resp = client.get("/redefinir-senha/qualquer")
    assert resp.status_code == 410


@rsps_lib.activate
def test_post_senhas_iguais_redefine_e_invalida(client):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tokens_senha/records", json={"items": [TOKEN_VALIDO]})
    patch_user = []
    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/users/records/al1",
                          callback=lambda r: (patch_user.append(json.loads(r.body)), (200, {}, json.dumps(USER)))[1],
                          content_type="application/json")
    invalidou = []
    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/tokens_senha/records/tk1",
                          callback=lambda r: (invalidou.append(json.loads(r.body)), (200, {}, json.dumps(TOKEN_VALIDO)))[1],
                          content_type="application/json")
    resp = client.post("/redefinir-senha/abc", data={"senha": "novasenha", "senha_confirmar": "novasenha"})
    assert resp.status_code == 200
    assert "sucesso" in resp.data.decode().lower()
    assert patch_user and patch_user[0]["password"] == "novasenha"
    assert invalidou and invalidou[0]["usado"] is True


@rsps_lib.activate
def test_post_senhas_diferentes_erro(client):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tokens_senha/records", json={"items": [TOKEN_VALIDO]})
    resp = client.post("/redefinir-senha/abc", data={"senha": "abcdef", "senha_confirmar": "diferente"})
    assert resp.status_code == 200
    assert "não coincidem" in resp.data.decode()


# ── Professor: redefinir / reenviar ─────────────────────────────────────────────

@rsps_lib.activate
def test_professor_redefinir_gera_token_e_envia(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/users/records/al1", json=USER)
    criou = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/tokens_senha/records",
                          callback=lambda r: (criou.append(json.loads(r.body)), (200, {}, json.dumps({"id": "t"})))[1],
                          content_type="application/json")
    with patch.object(app_mod, "email_redefinir_senha", return_value=True) as mock_email:
        resp = client.post("/professor/aluno/al1/redefinir-senha")
    assert resp.status_code == 200
    assert "enviado" in resp.data.decode().lower()
    assert criou and criou[0]["aluno_id"] == "al1" and criou[0]["usado"] is False
    assert mock_email.called
    # link contém o token gerado
    assert criou[0]["token"] in mock_email.call_args.args[2]


@rsps_lib.activate
def test_professor_reenviar_gera_senha_e_envia(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/users/records/al1", json=USER)
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/users/records/al1", json=USER)
    with patch.object(app_mod, "email_boas_vindas", return_value=True) as mock_email:
        resp = client.post("/professor/aluno/al1/reenviar-boas-vindas", data={"turma_nome": "5TACN1"})
    assert resp.status_code == 200
    assert "email enviado" in resp.data.decode().lower()
    assert mock_email.called


# ── Cadastro manual de aluno ────────────────────────────────────────────────────

@rsps_lib.activate
def test_criar_aluno_manual_cria_user_matricula_e_email(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01",
                 json={"id": "turma01", "nome": "5TACN1"})
    user_cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/users/records",
                          callback=lambda r: (user_cap.append(json.loads(r.body)), (200, {}, json.dumps({"id": "novo1"})))[1],
                          content_type="application/json")
    mat_cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/matriculas/records",
                          callback=lambda r: (mat_cap.append(json.loads(r.body)), (200, {}, json.dumps({"id": "m1"})))[1],
                          content_type="application/json")
    with patch.object(app_mod, "email_boas_vindas", return_value=True) as mock_email:
        resp = client.post("/professor/turma/turma01/alunos/novo", data={
            "nome": "Maria", "email": "maria@x.com", "senha": "temp1234",
            "whatsapp": "71999", "enviar_email": "on"})
    assert resp.status_code in (200, 302)
    assert user_cap and user_cap[0]["email"] == "maria@x.com" and user_cap[0]["role"] == "aluno"
    assert mat_cap and mat_cap[0]["turma"] == "turma01" and mat_cap[0]["origem"] == "manual"
    assert mock_email.called


@rsps_lib.activate
def test_criar_aluno_manual_sem_email_nao_envia(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01",
                 json={"id": "turma01", "nome": "5TACN1"})
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/users/records", json={"id": "novo1"})
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/matriculas/records", json={"id": "m1"})
    with patch.object(app_mod, "email_boas_vindas", return_value=True) as mock_email:
        resp = client.post("/professor/turma/turma01/alunos/novo", data={
            "nome": "Maria", "email": "maria@x.com", "senha": "temp1234"})  # sem enviar_email
    assert resp.status_code in (200, 302)
    assert not mock_email.called
