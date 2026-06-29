"""Testes de integração para o portal de turma/disciplina."""
import responses as rsps_lib

PB = "http://pb.test"

TURMA = {"id": "turma01", "nome": "1º Ano EMI", "modalidade": "EMI", "ano": "2025"}
DISCIPLINA = {"id": "disc01", "nome": "Hematologia"}

ATIVIDADE = {
    "id": "ativ01",
    "titulo": "Quiz Hematologia",
    "questoes": ["q001mc4"],
    "ativa": True,
    "disponivel_de": None,
    "disponivel_ate": None,
    "tempo_limite": 0,
    "disciplina": "disc01",
    "expand": {"disciplina": DISCIPLINA},
}

MATERIAL_VIDEO = {
    "id": "mat01",
    "titulo": "Introdução ao LIS",
    "tipo": "video",
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "descricao": "Aula introdutória",
    "ordem": 1,
    "ativo": True,
}

MATERIAL_PDF = {
    "id": "mat02",
    "titulo": "Apostila LIS 2025",
    "tipo": "pdf",
    "url": "https://example.com/apostila.pdf",
    "descricao": "",
    "ordem": 2,
    "ativo": True,
}

MATERIAL_LINK = {
    "id": "mat03",
    "titulo": "Portal Pixeon",
    "tipo": "link",
    "url": "https://pixeon.com",
    "descricao": "Sistema de informação hospitalar",
    "ordem": 3,
    "ativo": True,
}


def _mock_portal(turma=TURMA, disciplina=DISCIPLINA, atividades=None, materiais=None):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=turma)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=disciplina)
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/materiais/records",
        json={"items": materiais or []},
    )
    # Always mock atividades: serves listar_disciplinas_da_turma (drawer) for every request,
    # and listar_atividades_por_disciplina (tab) when logged in. responses lib reuses the
    # same mock for all matching GET requests to this URL.
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/atividades/records",
        json={"items": atividades if atividades is not None else [ATIVIDADE]},
    )


@rsps_lib.activate
def test_portal_retorna_200_sem_login(client):
    _mock_portal(materiais=[MATERIAL_VIDEO])
    resp = client.get("/turma/turma01/disc01")
    assert resp.status_code == 200


@rsps_lib.activate
def test_portal_retorna_200_com_login(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok123"
        sess["aluno_nome"] = "Lucas"
    _mock_portal(atividades=[ATIVIDADE], materiais=[MATERIAL_PDF])
    resp = client.get("/turma/turma01/disc01")
    assert resp.status_code == 200


@rsps_lib.activate
def test_portal_sem_login_mostra_bloqueio_atividades(client):
    _mock_portal(materiais=[])
    resp = client.get("/turma/turma01/disc01")
    html = resp.data.decode()
    assert "Faça login" in html or "login" in html.lower()


@rsps_lib.activate
def test_portal_materiais_carregam_sem_autenticacao(client):
    _mock_portal(materiais=[MATERIAL_VIDEO, MATERIAL_PDF, MATERIAL_LINK])
    resp = client.get("/turma/turma01/disc01")
    html = resp.data.decode()
    assert "Introdução ao LIS" in html
    assert "Apostila LIS 2025" in html
    assert "Portal Pixeon" in html


@rsps_lib.activate
def test_portal_embed_youtube_renderiza(client):
    _mock_portal(materiais=[MATERIAL_VIDEO])
    resp = client.get("/turma/turma01/disc01")
    html = resp.data.decode()
    assert "youtube.com/embed/dQw4w9WgXcQ" in html
    assert "<iframe" in html


@rsps_lib.activate
def test_portal_pdf_abre_em_nova_aba(client):
    _mock_portal(materiais=[MATERIAL_PDF])
    resp = client.get("/turma/turma01/disc01")
    html = resp.data.decode()
    assert 'target="_blank"' in html
    assert "apostila.pdf" in html


@rsps_lib.activate
def test_portal_atividade_disponivel_com_login(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok123"
        sess["aluno_nome"] = "Lucas"
    _mock_portal(atividades=[ATIVIDADE], materiais=[])
    resp = client.get("/turma/turma01/disc01")
    html = resp.data.decode()
    assert "Quiz Hematologia" in html
    assert "/atividade/ativ01" in html


@rsps_lib.activate
def test_portal_atividade_encerrada_mostra_badge(client):
    ativ_enc = {**ATIVIDADE, "disponivel_ate": "2020-01-01T00:00:00Z"}
    with client.session_transaction() as sess:
        sess["token"] = "tok123"
        sess["aluno_nome"] = "Lucas"
    _mock_portal(atividades=[ativ_enc], materiais=[])
    resp = client.get("/turma/turma01/disc01")
    html = resp.data.decode()
    assert "Encerrada" in html


@rsps_lib.activate
def test_portal_drawer_contem_disciplinas_e_navegacao(client):
    _mock_portal(materiais=[])
    resp = client.get("/turma/turma01/disc01")
    html = resp.data.decode()
    # Drawer exists and has the discipline link
    assert "nav-drawer" in html
    assert "Hematologia" in html
    assert 'href="/turma/turma01/disc01"' in html
    # Link home presente no drawer
    assert 'href="/"' in html
    # Hamburger button presente
    assert "nav-toggle-btn" in html


@rsps_lib.activate
def test_portal_drawer_marca_disciplina_ativa(client):
    _mock_portal(materiais=[])
    resp = client.get("/turma/turma01/disc01")
    html = resp.data.decode()
    # Current discipline link should have the active class
    assert 'nav-link active' in html or 'class="nav-link active"' in html
