"""Testes de integração para o sistema de tentativas."""
import responses as rsps_lib

PB = "http://pb.test"

ATIVIDADE = {
    "id": "ativ01",
    "titulo": "Quiz Hematologia",
    "questoes": ["q001"],
    "ativa": True,
    "disponivel_de": None,
    "disponivel_ate": None,
    "tempo_limite": 0,
    "disciplina": "disc01",
    "max_tentativas": 2,
    "nota_automatica": True,
    "expand": {"disciplina": {"id": "disc01", "nome": "Hematologia"}},
}

TENTATIVA_REC = {"id": "tent01"}

TENTATIVA_CONCLUIDA = {
    "id": "tent01",
    "disciplina": "ativ01",
    "aluno_id": "aluno01",
    "aluno_nome": "Lucas",
    "numero_tentativa": 1,
    "concluida": True,
    "nota_liberada": True,
    "score_percentual": 80,
}

QUESTAO_MC = {
    "id": "q001",
    "tipo": "mc4",
    "enunciado": "Qual é a função dos eritrócitos?",
    "alternativas": [
        {"id": "a1", "letra": "A", "texto": "Transportar oxigênio", "correta": True},
        {"id": "a2", "letra": "B", "texto": "Combater infecções", "correta": False},
        {"id": "a3", "letra": "C", "texto": "Coagular sangue", "correta": False},
        {"id": "a4", "letra": "D", "texto": "Produzir anticorpos", "correta": False},
    ],
}


def _mock_atividade_start(ativ=None, tentativa_response=None, tentativas_existentes=None):
    """Mock all PocketBase calls for GET /atividade/<id>."""
    a = ativ or ATIVIDADE
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/{a['id']}", json=a)
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/tentativas/records",
        json={"items": tentativas_existentes or []},
    )
    rsps_lib.add(
        rsps_lib.POST,
        f"{PB}/api/collections/tentativas/records",
        json=tentativa_response or TENTATIVA_REC,
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/questoes/records/q001",
        json=QUESTAO_MC,
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/alternativas/records",
        json={"items": QUESTAO_MC["alternativas"]},
    )


@rsps_lib.activate
def test_atividade_cria_tentativa_na_sessao(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok123"
        sess["aluno_id"] = "aluno01"
        sess["aluno_nome"] = "Lucas"
    _mock_atividade_start()
    resp = client.get("/atividade/ativ01")
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("tentativa_id") == "tent01"
        assert sess.get("nota_automatica") is True
        assert sess.get("max_tentativas") == 2


@rsps_lib.activate
def test_atividade_bloqueada_quando_tentativas_esgotadas(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok123"
        sess["aluno_id"] = "aluno01"
        sess["aluno_nome"] = "Lucas"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/tentativas/records",
        json={"items": [TENTATIVA_CONCLUIDA, {**TENTATIVA_CONCLUIDA, "id": "tent02", "numero_tentativa": 2}]},
    )
    resp = client.get("/atividade/ativ01")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "esgotada" in html or "indisponível" in html.lower() or "Indisponível" in html


@rsps_lib.activate
def test_status_atividade_retorna_json(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok123"
        sess["aluno_id"] = "aluno01"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/tentativas/records",
        json={"items": [TENTATIVA_CONCLUIDA]},
    )
    resp = client.get("/aluno/atividade/ativ01/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["tentativas_usadas"] == 1
    assert data["max_tentativas"] == 2
    assert data["pode_tentar"] is True
    assert data["melhor_nota"] == 80
    assert data["nota_liberada"] is True


@rsps_lib.activate
def test_liberar_nota_patch(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok123"
    rsps_lib.add(
        rsps_lib.PATCH,
        f"{PB}/api/collections/tentativas/records/tent01",
        json={"id": "tent01", "nota_liberada": True},
    )
    resp = client.post("/professor/atividade/ativ01/liberar-nota/tent01")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


@rsps_lib.activate
def test_placar_mostra_nota_automatica(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok123"
        sess["aluno_id"] = "aluno01"
        sess["ativ_id"] = "ativ01"
        sess["fila"] = []
        sess["respostas"] = [{"score_raw": 8, "score_max": 10}]
        sess["total"] = 1
        sess["nota_automatica"] = True
        sess["tentativa_id"] = "tent01"
        sess["max_tentativas"] = 2
        sess["tentativa_concluida"] = False
    rsps_lib.add(
        rsps_lib.PATCH,
        f"{PB}/api/collections/tentativas/records/tent01",
        json={"id": "tent01", "concluida": True},
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/tentativas/records",
        json={"items": [TENTATIVA_CONCLUIDA]},
    )
    resp = client.get("/htmx/proxima/ativ01")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Nota:" in html or "80%" in html


@rsps_lib.activate
def test_placar_mostra_aguardando_correcao(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok123"
        sess["aluno_id"] = "aluno01"
        sess["ativ_id"] = "ativ01"
        sess["fila"] = []
        sess["respostas"] = [{"score_raw": 5, "score_max": 10}]
        sess["total"] = 1
        sess["nota_automatica"] = False
        sess["tentativa_id"] = "tent01"
        sess["max_tentativas"] = 0
        sess["tentativa_concluida"] = False
    rsps_lib.add(
        rsps_lib.PATCH,
        f"{PB}/api/collections/tentativas/records/tent01",
        json={"id": "tent01", "concluida": True},
    )
    resp = client.get("/htmx/proxima/ativ01")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "correção" in html or "Aguardando" in html


@rsps_lib.activate
def test_placar_nao_conclui_tentativa_duas_vezes(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok123"
        sess["aluno_id"] = "aluno01"
        sess["ativ_id"] = "ativ01"
        sess["fila"] = []
        sess["respostas"] = [{"score_raw": 10, "score_max": 10}]
        sess["total"] = 1
        sess["nota_automatica"] = True
        sess["tentativa_id"] = "tent01"
        sess["max_tentativas"] = 0
        sess["tentativa_concluida"] = True  # already concluded
    # No PATCH mock — if PATCH is called, responses raises ConnectionError
    resp = client.get("/htmx/proxima/ativ01")
    assert resp.status_code == 200
