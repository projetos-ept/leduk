"""Testes de integração para as 5 melhorias de UX do portal."""
import responses as rsps_lib

PB = "http://pb.test"

DISCIPLINA = {"id": "disc01", "nome": "Hematologia"}
ATIVIDADE = {
    "id": "ativ01",
    "titulo": "Quiz Hematologia",
    "questoes": ["q001", "q002", "q003", "q004"],
    "ativa": True,
    "disponivel_de": None,
    "disponivel_ate": None,
    "tempo_limite": 0,
    "disciplina": "disc01",
    "max_tentativas": 2,
    "nota_automatica": True,
    "exibir_feedback_pos": True,
    "expand": {"disciplina": DISCIPLINA},
}
TURMA = {"id": "turma01", "nome": "1º Ano EMI", "modalidade": "EMI", "ano": "2025"}
TENTATIVA_CONCLUIDA = {
    "id": "tent01",
    "disciplina": "ativ01",
    "aluno_id": "aluno01",
    "aluno_nome": "Lucas",
    "numero_tentativa": 1,
    "concluida": True,
    "nota_liberada": True,
    "score_percentual": 75,
    "created": "2026-06-28T10:00:00Z",
}
TENTATIVA_EM_ANDAMENTO = {
    "id": "tent02",
    "disciplina": "ativ01",
    "aluno_id": "aluno01",
    "concluida": False,
    "questoes_respondidas": 3,
}
QUESTAO_MC = {
    "id": "q001",
    "tipo": "mc4",
    "enunciado": "Qual é a função dos eritrócitos?",
    "explicacao": "Eritrócitos transportam oxigênio.",
    "alternativas": [
        {"id": "a1", "letra": "A", "texto": "Transportar oxigênio", "correta": True},
        {"id": "a2", "letra": "B", "texto": "Combater infecções", "correta": False},
        {"id": "a3", "letra": "C", "texto": "Coagular sangue", "correta": False},
        {"id": "a4", "letra": "D", "texto": "Produzir anticorpos", "correta": False},
    ],
}


# ── Item 1: Progresso visual ──────────────────────────────────────────────────

def _mock_portal_base(atividades=None, materiais=None):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=DISCIPLINA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/materiais/records", json={"items": materiais or []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records", json={"items": atividades or [ATIVIDADE]})


@rsps_lib.activate
def test_card_mostra_progresso_em_andamento(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["aluno_id"] = "aluno01"
        sess["aluno_nome"] = "Lucas"
    _mock_portal_base(atividades=[ATIVIDADE])
    # status_atividade_aluno: concluidas=0 → disponivel
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": []})                                         # listar_tentativas_aluno
    # progresso_tentativa_atual: há tentativa em andamento
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_EM_ANDAMENTO]})
    resp = client.get("/turma/turma01/disc01")
    html = resp.data.decode()
    assert "3 de 4 respondidas" in html
    assert "Continuar" in html


# ── Item 2: Histórico ─────────────────────────────────────────────────────────

@rsps_lib.activate
def test_historico_retorna_200(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["aluno_id"] = "aluno01"
        sess["aluno_nome"] = "Lucas"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_CONCLUIDA]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={**ATIVIDADE, "expand": {"disciplina": DISCIPLINA}})
    resp = client.get("/aluno/historico")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Meu Histórico" in html


@rsps_lib.activate
def test_historico_mostra_tentativas(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["aluno_id"] = "aluno01"
        sess["aluno_nome"] = "Lucas"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_CONCLUIDA]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={**ATIVIDADE, "expand": {"disciplina": DISCIPLINA}})
    resp = client.get("/aluno/historico")
    html = resp.data.decode()
    assert "Quiz Hematologia" in html
    assert "Tentativa 1" in html
    assert "75%" in html


# ── Item 3: Revisão / gabarito ────────────────────────────────────────────────

@rsps_lib.activate
def test_revisao_retorna_200_quando_habilitada(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["aluno_id"] = "aluno01"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records/tent01",
                 json=TENTATIVA_CONCLUIDA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": []})  # listar_respostas_tentativa
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001", json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q002", json={**QUESTAO_MC, "id": "q002"})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q003", json={**QUESTAO_MC, "id": "q003"})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q004", json={**QUESTAO_MC, "id": "q004"})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})
    resp = client.get("/aluno/atividade/ativ01/revisao/tent01")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Qual é a função dos eritrócitos?" in html


@rsps_lib.activate
def test_revisao_retorna_403_quando_desabilitada(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["aluno_id"] = "aluno01"
    ativ_sem_feedback = {**ATIVIDADE, "exibir_feedback_pos": False}
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json=ativ_sem_feedback)
    resp = client.get("/aluno/atividade/ativ01/revisao/tent01")
    assert resp.status_code == 403
    assert "não está disponível" in resp.data.decode()


@rsps_lib.activate
def test_placar_exibe_botao_gabarito(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["aluno_id"] = "aluno01"
        sess["ativ_id"] = "ativ01"
        sess["fila"] = []
        sess["respostas"] = [{"score_raw": 4, "score_max": 4}]
        sess["total"] = 1
        sess["nota_automatica"] = True
        sess["tentativa_id"] = "tent01"
        sess["max_tentativas"] = 0
        sess["tentativa_concluida"] = True
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    resp = client.get("/htmx/proxima/ativ01")
    html = resp.data.decode()
    assert "Ver gabarito" in html
    assert "/revisao/tent01" in html


@rsps_lib.activate
def test_placar_sem_botao_gabarito_quando_desabilitado(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["aluno_id"] = "aluno01"
        sess["ativ_id"] = "ativ01"
        sess["fila"] = []
        sess["respostas"] = [{"score_raw": 2, "score_max": 4}]
        sess["total"] = 1
        sess["nota_automatica"] = True
        sess["tentativa_id"] = "tent01"
        sess["max_tentativas"] = 0
        sess["tentativa_concluida"] = True
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={**ATIVIDADE, "exibir_feedback_pos": False})
    resp = client.get("/htmx/proxima/ativ01")
    html = resp.data.decode()
    assert "Ver gabarito" not in html


# ── Item 4: Badge de novas atividades ────────────────────────────────────────

@rsps_lib.activate
def test_badge_novas_atividades_aparece(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["aluno_id"] = "aluno01"
        sess["aluno_nome"] = "Lucas"
        sess["ultimo_acesso"] = "2026-01-01T00:00:00+00:00"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records",
                 json={"items": [TURMA]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": [ATIVIDADE]})   # listar_atividades_por_turma
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": [ATIVIDADE]})   # contar_novas_atividades
    resp = client.get("/")
    html = resp.data.decode()
    assert "badge-novo" in html


@rsps_lib.activate
def test_badge_novas_nao_aparece_sem_ultimo_acesso(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["aluno_id"] = "aluno01"
        sess["aluno_nome"] = "Lucas"
        # sem ultimo_acesso
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records",
                 json={"items": [TURMA]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": [ATIVIDADE]})
    resp = client.get("/")
    html = resp.data.decode()
    assert "badge-novo" not in html


# ── Item 5: Revisão no card realizada ────────────────────────────────────────

@rsps_lib.activate
def test_card_realizada_exibe_link_gabarito(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["aluno_id"] = "aluno01"
        sess["aluno_nome"] = "Lucas"
    _mock_portal_base(atividades=[ATIVIDADE])
    # status_atividade_aluno: 2 tentativas concluidas → realizada
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_CONCLUIDA, {**TENTATIVA_CONCLUIDA, "id": "tent02"}]})
    resp = client.get("/turma/turma01/disc01")
    html = resp.data.decode()
    assert "Ver gabarito" in html
    assert "/revisao/" in html
