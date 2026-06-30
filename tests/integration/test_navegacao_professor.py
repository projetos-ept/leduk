"""Testes de navegação do professor: drawer dedicado + atalhos ao banco."""
import responses as rsps_lib

PB = "http://pb.test"

TURMA = {"id": "turma01", "nome": "5TACN1", "modalidade": "PROEJA"}
DISCIPLINA = {"id": "disc01", "nome": "Informática Aplicada"}
# atividade com disciplina expandida — fonte das disciplinas para drawer/dashboard
ATIVIDADE = {
    "id": "ativ01", "titulo": "Prova 1", "turma": "turma01", "disciplina": "disc01",
    "ativa": True, "questoes": ["q001"],
    "expand": {"disciplina": DISCIPLINA},
}


def _sess_prof(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok-prof"
        sess["role"] = "professor"
        sess["aluno_nome"] = "Lucas Batista"


def _sess_aluno(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok-aluno"
        sess["role"] = "aluno"
        sess["aluno_nome"] = "Aluno Teste"


def _mock_dashboard():
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records",
                 json={"items": [TURMA]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": [ATIVIDADE]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": []})


# ── Drawer do professor ─────────────────────────────────────────────────────────

@rsps_lib.activate
def test_drawer_professor_aparece_no_dashboard(client):
    _sess_prof(client)
    _mock_dashboard()
    resp = client.get("/professor/dashboard")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'class="nav-drawer"' in html
    assert "Menu — Professor" in html
    assert "Minhas turmas" in html
    assert "Portal do Aluno" in html


@rsps_lib.activate
def test_drawer_lista_banco_questoes_da_disciplina(client):
    _sess_prof(client)
    _mock_dashboard()
    resp = client.get("/professor/dashboard")
    html = resp.data.decode()
    # atalho direto ao banco da disciplina dentro do drawer
    assert "/professor/disciplina/disc01/banco-questoes" in html
    assert "Informática Aplicada" in html


@rsps_lib.activate
def test_hamburguer_presente_em_pagina_do_professor(client):
    _sess_prof(client)
    _mock_dashboard()
    resp = client.get("/professor/dashboard")
    html = resp.data.decode()
    assert 'class="nav-toggle-btn"' in html
    assert 'for="nav-toggle"' in html


# ── Conteúdo de aluno vs professor ──────────────────────────────────────────────

@rsps_lib.activate
def test_drawer_professor_ausente_para_aluno_no_portal(client):
    """No portal (página do aluno), não aparece o drawer de professor."""
    _sess_aluno(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01",
                 json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01",
                 json=DISCIPLINA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": [ATIVIDADE]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/materiais/records",
                 json={"items": []})
    resp = client.get("/turma/turma01/disc01")
    assert resp.status_code == 200
    html = resp.data.decode()
    # o portal tem seu próprio drawer de aluno, mas não o menu de professor
    assert "Menu — Professor" not in html


def test_aluno_nao_acessa_paginas_professor(client):
    _sess_aluno(client)
    resp = client.get("/professor/dashboard")
    assert resp.status_code == 302


# ── Atalhos ao banco no dashboard e na turma ────────────────────────────────────

@rsps_lib.activate
def test_dashboard_card_tem_link_banco_disciplina(client):
    _sess_prof(client)
    _mock_dashboard()
    resp = client.get("/professor/dashboard")
    html = resp.data.decode()
    assert "/professor/disciplina/disc01/banco-questoes" in html
    # rótulo do atalho no card
    assert "Questões" in html


@rsps_lib.activate
def test_turma_tem_barra_banco_questoes(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01",
                 json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": [ATIVIDADE]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
                 json={"items": [DISCIPLINA]})
    resp = client.get("/professor/turma/turma01")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Banco de questões" in html
    assert "/professor/disciplina/disc01/banco-questoes" in html
