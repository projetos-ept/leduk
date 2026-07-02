"""Testes de integração para rotas HTMX de interação (POST /htmx/responder)."""
import responses as rsps_lib
import pytest


PB = "http://pb.test"


@rsps_lib.activate
def test_responder_mc_correto(client, questao_mc4):
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/questoes/records/q001mc4",
        json=questao_mc4,
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/alternativas/records",
        json={"items": questao_mc4["alternativas"]},
    )

    resp = client.post(
        "/htmx/responder",
        data={"tipo": "mc4", "questao_id": "q001mc4", "resposta": "A"},
    )
    assert resp.status_code == 200


@rsps_lib.activate
def test_responder_mc_errado(client, questao_mc4):
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/questoes/records/q001mc4",
        json=questao_mc4,
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/alternativas/records",
        json={"items": questao_mc4["alternativas"]},
    )

    resp = client.post(
        "/htmx/responder",
        data={"tipo": "mc4", "questao_id": "q001mc4", "resposta": "B"},
    )
    assert resp.status_code == 200


@rsps_lib.activate
def test_responder_vf(client, questao_vf):
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/questoes/records/q002vf",
        json=questao_vf,
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/itens_vf/records",
        json={"items": questao_vf["itens_vf"]},
    )

    resp = client.post(
        "/htmx/responder",
        data={
            "tipo": "vf",
            "questao_id": "q002vf",
            "vf_1": "true",
            "vf_2": "false",
            "vf_3": "true",
        },
    )
    assert resp.status_code == 200


@rsps_lib.activate
def test_responder_associativa(client, questao_associativa):
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/questoes/records/q003assoc",
        json=questao_associativa,
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/pares_associativos/records",
        json={"items": questao_associativa["pares_associativos"]},
    )

    resp = client.post(
        "/htmx/responder",
        data={
            "tipo": "associativa",
            "questao_id": "q003assoc",
            "par_1": "Glicose",
            "par_2": "Ureia",
            "par_3": "Aspartato aminotransferase",
            "par_4": "Creatinina",
        },
    )
    assert resp.status_code == 200


def test_responder_tipo_invalido(client):
    resp = client.post(
        "/htmx/responder",
        data={"tipo": "desconhecido", "questao_id": "xxx"},
    )
    assert resp.status_code == 400


@rsps_lib.activate
def test_questao_mc_embaralha_alternativas(client, questao_mc4):
    """Alternativas são exibidas em ordem diferente da original (embaralhada)
    e o set de letras permanece completo."""
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/questoes/records/q001mc4",
        json=questao_mc4,
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/alternativas/records",
        json={"items": questao_mc4["alternativas"]},
    )
    with client.session_transaction() as sess:
        sess["tentativa_id"] = "tent-shuffle-test"
        sess["total"] = 1
        sess["fila"] = []
        sess["ativ_id"] = "ativ01"

    resp = client.get("/htmx/questao/q001mc4")
    assert resp.status_code == 200
    html = resp.data.decode()

    # todas as letras aparecem na resposta
    for letra in ("A", "B", "C", "D"):
        assert f'value="{letra}"' in html

    # a ordem de exibição deve diferir da original [A,B,C,D] com este seed
    import re
    letras_exibidas = re.findall(r'value="([A-E])"', html)
    assert sorted(letras_exibidas) == ["A", "B", "C", "D"]
    # com seed "tent-shuffle-testq001mc4" a ordem não é A,B,C,D
    assert letras_exibidas != ["A", "B", "C", "D"]


# ── Modo prova ────────────────────────────────────────────────────────────────

@rsps_lib.activate
def test_modo_prova_feedback_auto_avanca_sem_mostrar_texto(client, questao_mc4):
    """Em modo_prova o feedback não exibe texto — só o bloco hx-trigger=load."""
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001mc4", json=questao_mc4)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": questao_mc4["alternativas"]})
    with client.session_transaction() as sess:
        sess["modo_prova"] = True
        sess["ativ_id"] = "ativ01"
        sess["respostas"] = []
        sess["total"] = 1
        sess["fila"] = []
    resp = client.post("/htmx/responder",
                       data={"tipo": "mc4", "questao_id": "q001mc4", "resposta": "A"})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'hx-trigger="load"' in html
    assert "Resposta correta" not in html
    assert "Resposta incorreta" not in html


@rsps_lib.activate
def test_modo_prova_false_exibe_feedback_normal(client, questao_mc4):
    """Sem modo_prova o feedback textual é exibido normalmente."""
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001mc4", json=questao_mc4)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": questao_mc4["alternativas"]})
    with client.session_transaction() as sess:
        sess["modo_prova"] = False
        sess["ativ_id"] = "ativ01"
        sess["respostas"] = []
        sess["total"] = 1
        sess["fila"] = []
    resp = client.post("/htmx/responder",
                       data={"tipo": "mc4", "questao_id": "q001mc4", "resposta": "A"})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'hx-trigger="load"' not in html
    assert "Resposta correta" in html or "Resposta incorreta" in html


@rsps_lib.activate
def test_modo_prova_placar_sem_botao_gabarito(client):
    """Em modo_prova o placar não exibe o link 'Ver gabarito'."""
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={"id": "ativ01", "exibir_feedback_pos": True, "nota_automatica": False})
    with client.session_transaction() as sess:
        sess["modo_prova"] = True
        sess["respostas"] = []
        sess["tentativa_id"] = "tent01"
        sess["nota_automatica"] = False
        sess["tentativa_concluida"] = True
        sess["max_tentativas"] = 0
    resp = client.get("/htmx/resultado/ativ01")
    assert resp.status_code == 200
    assert "Ver gabarito" not in resp.data.decode()


@rsps_lib.activate
def test_modo_prova_false_placar_exibe_botao_gabarito(client):
    """Sem modo_prova e com exibir_feedback_pos o link 'Ver gabarito' aparece."""
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={"id": "ativ01", "exibir_feedback_pos": True, "nota_automatica": False})
    with client.session_transaction() as sess:
        sess["modo_prova"] = False
        sess["respostas"] = []
        sess["tentativa_id"] = "tent01"
        sess["nota_automatica"] = False
        sess["tentativa_concluida"] = True
        sess["max_tentativas"] = 0
    resp = client.get("/htmx/resultado/ativ01")
    assert resp.status_code == 200
    assert "Ver gabarito" in resp.data.decode()


@rsps_lib.activate
def test_modo_prova_placar_oculta_detalhamento(client):
    """Em modo_prova o detalhamento por questão e 'Aguardando correção' não aparecem."""
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={"id": "ativ01", "exibir_feedback_pos": False,
                       "nota_automatica": False, "valor_total": 10.0,
                       "questoes": ["q1"]})
    respostas = [{"score_raw": 0, "score_max": 1, "correta": False, "_peso": 1, "_num": 1}]
    with client.session_transaction() as sess:
        sess["modo_prova"] = True
        sess["respostas"] = respostas
        sess["tentativa_id"] = "tent01"
        sess["nota_automatica"] = False
        sess["tentativa_concluida"] = True
        sess["max_tentativas"] = 0
    resp = client.get("/htmx/resultado/ativ01")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Detalhamento por questão" not in html
    assert "Aguardando correção" not in html
    assert "questão correta" not in html


@rsps_lib.activate
def test_modo_prova_false_placar_exibe_detalhamento(client):
    """Sem modo_prova o detalhamento por questão é exibido normalmente."""
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={"id": "ativ01", "exibir_feedback_pos": False,
                       "nota_automatica": False, "valor_total": 10.0,
                       "questoes": ["q1"]})
    respostas = [{"score_raw": 1, "score_max": 1, "correta": True, "_peso": 1, "_num": 1}]
    with client.session_transaction() as sess:
        sess["modo_prova"] = False
        sess["respostas"] = respostas
        sess["tentativa_id"] = "tent01"
        sess["nota_automatica"] = False
        sess["tentativa_concluida"] = True
        sess["max_tentativas"] = 0
    resp = client.get("/htmx/resultado/ativ01")
    assert resp.status_code == 200
    assert "Detalhamento por questão" in resp.data.decode()
