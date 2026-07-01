"""Fluxo público de cadastro via link de convite + gestão do formulário."""
import json
from unittest.mock import patch

import responses as rsps_lib

import app as app_mod

PB = "http://pb.test"

TURMA = {"id": "turma01", "nome": "5TACN1", "modalidade": "PROEJA"}
FORM_ATIVO = {"id": "f1", "turma": "turma01", "token": "abc", "ativo": True,
              "expand": {"turma": TURMA}}
FORM_INATIVO = {"id": "f1", "turma": "turma01", "token": "abc", "ativo": False,
                "expand": {"turma": TURMA}}


def _sess_prof(client):
    with client.session_transaction() as s:
        s["token"] = "tok"; s["role"] = "professor"; s["aluno_nome"] = "Prof"


# ── GET público ─────────────────────────────────────────────────────────────────

@rsps_lib.activate
def test_get_cadastro_valido_200(client):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/formularios_cadastro/records",
                 json={"items": [FORM_ATIVO]})
    resp = client.get("/cadastro/abc")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Cadastro" in html and "5TACN1" in html


@rsps_lib.activate
def test_get_cadastro_token_invalido_404(client):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/formularios_cadastro/records",
                 json={"items": []})
    resp = client.get("/cadastro/naoexiste")
    assert resp.status_code == 404


@rsps_lib.activate
def test_get_cadastro_inativo_pagina_inativo(client):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/formularios_cadastro/records",
                 json={"items": [FORM_INATIVO]})
    resp = client.get("/cadastro/abc")
    assert resp.status_code == 200
    assert "não está mais disponível" in resp.data.decode()


# ── POST público ────────────────────────────────────────────────────────────────

@rsps_lib.activate
def test_post_cadastro_valido_cria_e_loga(client):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/formularios_cadastro/records",
                 json={"items": [FORM_ATIVO]})
    user_cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/users/records",
                          callback=lambda r: (user_cap.append(json.loads(r.body)), (200, {}, json.dumps({"id": "al9", "name": "Ana"})))[1],
                          content_type="application/json")
    mat_cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/matriculas/records",
                          callback=lambda r: (mat_cap.append(json.loads(r.body)), (200, {}, json.dumps({"id": "m1"})))[1],
                          content_type="application/json")
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/users/auth-with-password",
                 json={"token": "jwt-al9", "record": {"id": "al9", "name": "Ana", "role": "aluno"}})
    with patch.object(app_mod, "email_boas_vindas", return_value=True):
        resp = client.post("/cadastro/abc", data={
            "nome": "Ana", "email": "ana@x.com", "senha": "senha123",
            "senha_confirmar": "senha123", "whatsapp": "71999"})
    assert resp.status_code == 302
    assert user_cap and user_cap[0]["email"] == "ana@x.com" and user_cap[0]["role"] == "aluno"
    assert mat_cap and mat_cap[0]["origem"] == "formulario"
    with client.session_transaction() as s:
        assert s.get("aluno_id") == "al9" and s.get("token") == "jwt-al9"


@rsps_lib.activate
def test_post_cadastro_email_duplicado_erro(client):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/formularios_cadastro/records",
                 json={"items": [FORM_ATIVO]})
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/users/records",
                 status=400, json={"code": 400, "message": "Failed to create."})
    mat = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/matriculas/records",
                          callback=lambda r: (mat.append(1), (200, {}, "{}"))[1],
                          content_type="application/json")
    resp = client.post("/cadastro/abc", data={
        "nome": "Ana", "email": "dup@x.com", "senha": "senha123", "senha_confirmar": "senha123"})
    assert resp.status_code == 422
    assert "já possui uma conta" in resp.data.decode()
    assert not mat  # nada criado


@rsps_lib.activate
def test_post_cadastro_senhas_diferentes_erro(client):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/formularios_cadastro/records",
                 json={"items": [FORM_ATIVO]})
    resp = client.post("/cadastro/abc", data={
        "nome": "Ana", "email": "ana@x.com", "senha": "senha123", "senha_confirmar": "outra"})
    assert resp.status_code == 422
    assert "não coincidem" in resp.data.decode()


# ── Professor: criar/toggle/relatório ───────────────────────────────────────────

@rsps_lib.activate
def test_criar_formulario_gera_token(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/formularios_cadastro/records",
                 json={"items": []})  # ainda não existe
    cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/formularios_cadastro/records",
                          callback=lambda r: (cap.append(json.loads(r.body)), (200, {}, json.dumps({"id": "f1"})))[1],
                          content_type="application/json")
    resp = client.post("/professor/turma/turma01/formulario/criar")
    assert resp.status_code in (200, 302)
    assert cap and cap[0]["ativo"] is True and len(cap[0]["token"]) > 20


@rsps_lib.activate
def test_toggle_formulario_desativa(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/formularios_cadastro/records",
                 json={"items": [FORM_ATIVO]})
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/formularios_cadastro/records/f1",
                 json=FORM_INATIVO)
    resp = client.post("/professor/turma/turma01/formulario/toggle")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Ativar" in html  # botão para reativar → está inativo


@rsps_lib.activate
def test_relatorio_lista_apenas_origem_formulario(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/matriculas/records", json={"items": [
        {"id": "m1", "origem": "formulario", "aluno": "a1",
         "expand": {"aluno": {"id": "a1", "name": "Via Formulário", "email": "f@x.com"}}},
        {"id": "m2", "origem": "manual", "aluno": "a2",
         "expand": {"aluno": {"id": "a2", "name": "Cadastro Manual", "email": "m@x.com"}}},
    ]})
    resp = client.get("/professor/turma/turma01/formulario/relatorio")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Via Formulário" in html
    assert "Cadastro Manual" not in html


@rsps_lib.activate
def test_editar_matricula_inline(client):
    _sess_prof(client)
    cap = []
    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/users/records/a1",
                          callback=lambda r: (cap.append(json.loads(r.body)), (200, {}, "{}"))[1],
                          content_type="application/json")
    resp = client.post("/professor/aluno/a1/matricula", data={"matricula": "2026001"})
    assert resp.status_code == 200
    assert cap and cap[0]["matricula"] == "2026001"
    assert "2026001" in resp.data.decode()
