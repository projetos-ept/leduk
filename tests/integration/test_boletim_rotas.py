"""Testes das rotas do boletim (config, toggles, notas, acesso do aluno)."""
import json

import responses as rsps_lib

PB = "http://pb.test"

TURMA = {"id": "turma01", "nome": "5TACN1", "modalidade": "PROEJA", "ano": "2026"}
DISCIPLINA = {"id": "disc01", "nome": "IATS"}
BOLETIM = {"id": "bol01", "turma": "turma01", "media_aprovacao": 5.0,
           "ativo": True, "liberado": False, "ano": 2026}
UNIDADE = {"id": "u1", "boletim": "bol01", "disciplina": "disc01", "numero": 1,
           "titulo": "I Unidade", "atividades": ["ativ01"], "rec_atividade": "",
           "rec_nota_manual": None}
ATIVIDADE = {"id": "ativ01", "titulo": "Prova 1", "turma": "turma01", "disciplina": "disc01",
             "ativa": True, "valor_total": 10, "expand": {"disciplina": DISCIPLINA}}
TENTATIVA = {"id": "t1", "atividade": "ativ01", "aluno_id": "al1", "aluno_nome": "João",
             "concluida": True, "nota_final": 7.5}


def _sess_prof(client):
    with client.session_transaction() as s:
        s["token"] = "tok-prof"; s["role"] = "professor"; s["aluno_nome"] = "Prof"


def _sess_aluno(client, aid="al1"):
    with client.session_transaction() as s:
        s["token"] = "tok-al"; s["role"] = "aluno"; s["aluno_id"] = aid; s["aluno_nome"] = "João"


def _mock_dados_boletim(boletim=BOLETIM):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/boletins/records", json={"items": [boletim]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/unidades/records", json={"items": [UNIDADE]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/recuperacao_final/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records", json={"items": [ATIVIDADE]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records", json={"items": [TENTATIVA]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": [DISCIPLINA]})


# ── Acesso do aluno ─────────────────────────────────────────────────────────────

@rsps_lib.activate
def test_aluno_boletim_403_se_nao_liberado(client):
    _sess_aluno(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/boletins/records",
                 json={"items": [{**BOLETIM, "liberado": False}]})
    resp = client.get("/aluno/boletim/turma01")
    assert resp.status_code == 403
    assert "não disponível" in resp.data.decode().lower()


@rsps_lib.activate
def test_aluno_boletim_liberado_mostra_notas(client):
    _sess_aluno(client)
    _mock_dados_boletim({**BOLETIM, "liberado": True})
    resp = client.get("/aluno/boletim/turma01")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Meu Boletim" in html
    assert "IATS" in html
    assert "7.5" in html
    assert "Aprovado" in html


# ── Toggles ─────────────────────────────────────────────────────────────────────

@rsps_lib.activate
def test_toggle_ativar(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/boletins/records",
                 json={"items": [{**BOLETIM, "ativo": False}]})
    cap = []
    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/boletins/records/bol01",
                          callback=lambda r: (cap.append(json.loads(r.body)), (200, {}, json.dumps(BOLETIM)))[1],
                          content_type="application/json")
    resp = client.post("/professor/turma/turma01/boletim/ativar")
    assert resp.status_code in (200, 302)
    assert cap and cap[0]["ativo"] is True


@rsps_lib.activate
def test_toggle_liberar(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/boletins/records",
                 json={"items": [{**BOLETIM, "liberado": False}]})
    cap = []
    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/boletins/records/bol01",
                          callback=lambda r: (cap.append(json.loads(r.body)), (200, {}, json.dumps(BOLETIM)))[1],
                          content_type="application/json")
    resp = client.post("/professor/turma/turma01/boletim/liberar")
    assert resp.status_code in (200, 302)
    assert cap and cap[0]["liberado"] is True


# ── Dashboard de notas (mapa de calor) ──────────────────────────────────────────

@rsps_lib.activate
def test_dashboard_notas_renderiza_mapa(client):
    _sess_prof(client)
    _mock_dados_boletim()
    resp = client.get("/professor/turma/turma01/boletim/notas")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "João" in html
    assert "IATS" in html
    assert "mapa-calor" in html
    assert "7.5" in html  # nota da unidade
    assert "Aprovado" in html


@rsps_lib.activate
def test_config_get_sem_boletim_mostra_form(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/boletins/records", json={"items": []})
    resp = client.get("/professor/turma/turma01/boletim")
    assert resp.status_code == 200
    assert "Criar boletim" in resp.data.decode()


@rsps_lib.activate
def test_config_post_cria_boletim(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/boletins/records", json={"items": []})
    cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/boletins/records",
                          callback=lambda r: (cap.append(json.loads(r.body)), (200, {}, json.dumps(BOLETIM)))[1],
                          content_type="application/json")
    resp = client.post("/professor/turma/turma01/boletim",
                       data={"media_aprovacao": "6.0", "ano": "2026", "ativo": "on"})
    assert resp.status_code in (200, 302)
    assert cap and cap[0]["media_aprovacao"] == 6.0
    assert cap[0]["ativo"] is True and cap[0]["liberado"] is False


@rsps_lib.activate
def test_criar_unidade(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/boletins/records", json={"items": [BOLETIM]})
    cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/unidades/records",
                          callback=lambda r: (cap.append(json.loads(r.body)), (200, {}, json.dumps(UNIDADE)))[1],
                          content_type="application/json")
    resp = client.post("/professor/turma/turma01/boletim/unidade/nova",
                       data={"disciplina": "disc01", "numero": "1", "titulo": "I Unidade",
                             "atividades": ["ativ01"], "rec_atividade": "", "rec_nota_manual": ""})
    assert resp.status_code in (200, 302)
    assert cap and cap[0]["disciplina"] == "disc01"
    assert cap[0]["atividades"] == ["ativ01"]
    assert cap[0]["numero"] == 1
