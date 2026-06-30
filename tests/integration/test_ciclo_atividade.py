"""Teste de integração: ciclo completo — responder questão → atividade salva → dashboard ok."""
import json

import responses as rsps_lib

PB = "http://pb.test"

ATIVIDADE = {
    "id": "ativ42",
    "titulo": "LIS Básico",
    "questoes": ["q001"],
    "ativa": True,
    "disponivel_de": None,
    "disponivel_ate": None,
    "tempo_limite": 0,
    "disciplina": "disc01",
    "max_tentativas": 3,
    "nota_automatica": True,
    "exibir_feedback_pos": True,
    "valor_total": 0,
}

QUESTAO_MC = {
    "id": "q001",
    "tipo": "mc4",
    "enunciado": "Qual alternativa correta?",
    "peso": 1,
    "alternativas": [
        {"id": "a1", "letra": "A", "texto": "Certa", "correta": True},
        {"id": "a2", "letra": "B", "texto": "Errada", "correta": False},
        {"id": "a3", "letra": "C", "texto": "Errada", "correta": False},
        {"id": "a4", "letra": "D", "texto": "Errada", "correta": False},
    ],
}

TURMA = {"id": "turma01", "nome": "1º EMI", "modalidade": "EMI", "ano": "2025"}


def _setup_session(client, role="aluno"):
    with client.session_transaction() as sess:
        sess["token"] = "tok-aluno"
        sess["aluno_id"] = "aluno01"
        sess["aluno_nome"] = "Maria"
        sess["role"] = role
        sess["ativ_id"] = "ativ42"
        sess["fila"] = ["q001"]
        sess["total"] = 1
        sess["respostas"] = []
        sess["tentativa_id"] = "tent99"
        sess["nota_automatica"] = True
        sess["max_tentativas"] = 3


@rsps_lib.activate
def test_htmx_responder_inclui_campo_atividade(client):
    """POST /htmx/responder deve enviar 'atividade' no corpo para o PocketBase."""
    _setup_session(client)

    # buscar_questao
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001",
                 json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})

    captured_bodies = []

    def capture_tentativa(request):
        body = json.loads(request.body)
        captured_bodies.append(body)
        return (200, {}, json.dumps({"id": "respXX", **body}))

    rsps_lib.add_callback(
        rsps_lib.POST,
        f"{PB}/api/collections/tentativas/records",
        callback=capture_tentativa,
        content_type="application/json",
    )

    # atualizar_progresso
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/tentativas/records/tent99",
                 json={"id": "tent99", "questoes_respondidas": 1})

    resp = client.post("/htmx/responder", data={"tipo": "mc4", "questao_id": "q001", "resposta": "A"})
    assert resp.status_code == 200

    assert len(captured_bodies) == 1, "registrar_tentativa deve ter sido chamado uma vez"
    body = captured_bodies[0]
    assert body.get("atividade") == "ativ42", (
        f"campo 'atividade' ausente ou errado no payload: {body}"
    )
    assert body.get("questao") == "q001"
    assert body.get("tentativa_id") == "tent99"


@rsps_lib.activate
def test_professor_dashboard_sem_erro_400(client):
    """GET /professor/dashboard carrega sem erro mesmo com tentativas que têm atividade."""
    with client.session_transaction() as sess:
        sess["token"] = "tok-prof"
        sess["role"] = "professor"
        sess["aluno_nome"] = "Prof. Ana"

    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records",
                 json={"items": [TURMA]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": [ATIVIDADE]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [
                     {
                         "id": "tent99",
                         "atividade": "ativ42",
                         "aluno_id": "aluno01",
                         "aluno_nome": "Maria",
                         "concluida": True,
                         "nota_liberada": True,
                         "score_percentual": 100,
                     }
                 ]})

    resp = client.get("/professor/dashboard")
    assert resp.status_code == 200
    assert "1º EMI" in resp.data.decode()


@rsps_lib.activate
def test_ciclo_responder_e_concluir(client):
    """Ciclo completo: responder → concluir tentativa → placar exibido."""
    _setup_session(client)

    # 1. Responder questão
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001",
                 json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/tentativas/records",
                 json={"id": "respXX", "atividade": "ativ42", "questao": "q001"})
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/tentativas/records/tent99",
                 json={"id": "tent99", "questoes_respondidas": 1})

    r1 = client.post("/htmx/responder", data={"tipo": "mc4", "questao_id": "q001", "resposta": "A"})
    assert r1.status_code == 200

    # 2. Solicitar resultado
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ42",
                 json=ATIVIDADE)
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/tentativas/records/tent99",
                 json={"id": "tent99", "concluida": True, "score_percentual": 100})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [
                     {"id": "tent99", "atividade": "ativ42", "concluida": True,
                      "score_percentual": 100, "nota_liberada": True}
                 ]})

    r2 = client.get("/htmx/resultado/ativ42")
    assert r2.status_code == 200
