"""Smoke tests: excluir/clonar atividade e CRUD do banco de questões."""
import json

import responses as rsps_lib

PB = "http://pb.test"

TURMA = {"id": "turma01", "nome": "1º EMI"}
DISCIPLINAS = [{"id": "disc01", "nome": "Hematologia"}]

ATIVIDADE = {
    "id": "ativ01",
    "titulo": "Prova Hematologia",
    "questoes": ["q001"],
    "ativa": False,
    "turma": "turma01",
    "disciplina": "disc01",
    "max_tentativas": 1,
    "nota_automatica": False,
    "exibir_feedback_pos": True,
    "embaralhar": False,
    "valor_total": 3.0,
    "tempo_limite": 0,
    "disponivel_de": None,
    "disponivel_ate": None,
    "descricao": "",
}

QUESTAO_MC = {
    "id": "q001",
    "tipo": "mc4",
    "enunciado": "Qual é a função dos eritrócitos?",
    "peso": 1,
    "dificuldade": "medio",
    "feedback_geral": "",
    "imagem": "",
    "alternativas": [
        {"id": "a1", "letra": "A", "texto": "Transportar O₂", "correta": True, "feedback": ""},
        {"id": "a2", "letra": "B", "texto": "Combater infecções", "correta": False, "feedback": ""},
        {"id": "a3", "letra": "C", "texto": "Coagular sangue", "correta": False, "feedback": ""},
        {"id": "a4", "letra": "D", "texto": "Produzir anticorpos", "correta": False, "feedback": ""},
    ],
}


def _sess_prof(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok-prof"
        sess["role"] = "professor"
        sess["aluno_nome"] = "Prof. Ana"


# ── Excluir atividade ─────────────────────────────────────────────────────────

@rsps_lib.activate
def test_excluir_atividade_redireciona_para_turma(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json=ATIVIDADE)
    rsps_lib.add(rsps_lib.DELETE, f"{PB}/api/collections/atividades/records/ativ01",
                 status=204, body="")
    # redirect target: professor_turma
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
                 json={"items": DISCIPLINAS})
    resp = client.post("/professor/atividade/ativ01/excluir")
    assert resp.status_code in (200, 302)


# ── Clonar atividade ──────────────────────────────────────────────────────────

@rsps_lib.activate
def test_clonar_atividade_cria_copia_inativa(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json=ATIVIDADE)

    captured = []

    def capture(req):
        captured.append(json.loads(req.body))
        return (200, {}, json.dumps({"id": "ativ02", **json.loads(req.body)}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/atividades/records",
                          callback=capture, content_type="application/json")
    # redirect target
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
                 json={"items": DISCIPLINAS})

    resp = client.post("/professor/atividade/ativ01/clonar")
    assert resp.status_code in (200, 302)
    assert captured, "POST de clonagem não foi feito"
    assert "cópia" in captured[0]["titulo"]
    assert captured[0]["ativa"] is False


# ── Banco de questões ─────────────────────────────────────────────────────────

@rsps_lib.activate
def test_questoes_lista_retorna_200(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json=ATIVIDADE)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001",
                 json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})
    resp = client.get("/professor/atividade/ativ01/questoes")
    assert resp.status_code == 200
    assert "Qual é a função dos eritrócitos?" in resp.data.decode()


@rsps_lib.activate
def test_questao_nova_mc4_cria_questao_e_alternativas(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={**ATIVIDADE, "questoes": []})

    questao_criada = []

    def capture_questao(req):
        questao_criada.append(json.loads(req.body))
        return (200, {}, json.dumps({"id": "qNOVA"}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/questoes/records",
                          callback=capture_questao, content_type="application/json")

    alternativas_criadas = []

    def capture_alt(req):
        alternativas_criadas.append(json.loads(req.body))
        return (200, {}, json.dumps({"id": f"alt{len(alternativas_criadas)}"}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/alternativas/records",
                          callback=capture_alt, content_type="application/json")

    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/atividades/records/ativ01",
                 json={**ATIVIDADE, "questoes": ["qNOVA"]})

    # redirect target: questoes list
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={**ATIVIDADE, "questoes": ["qNOVA"]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/qNOVA",
                 json={**QUESTAO_MC, "id": "qNOVA"})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})

    resp = client.post("/professor/atividade/ativ01/questoes/nova", data={
        "tipo": "mc4",
        "enunciado": "Qual é a função dos eritrócitos?",
        "peso": "1",
        "dificuldade": "medio",
        "feedback_geral": "",
        "correta": "A",
        "alt_texto_A": "Transportar O₂",
        "alt_texto_B": "Combater infecções",
        "alt_texto_C": "Coagular sangue",
        "alt_texto_D": "Produzir anticorpos",
    })
    assert resp.status_code in (200, 302)
    assert questao_criada, "questão não foi criada"
    assert questao_criada[0]["tipo"] == "mc4"
    assert len(alternativas_criadas) == 4
    assert any(a["correta"] is True and a["letra"] == "A" for a in alternativas_criadas)


@rsps_lib.activate
def test_excluir_questao_remove_da_atividade(client):
    _sess_prof(client)
    # cascade: busca atividades que referenciam q001 e limpa o vínculo
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": [ATIVIDADE]})

    patch_body = []

    def capture_patch(req):
        patch_body.append(json.loads(req.body))
        return (200, {}, json.dumps(ATIVIDADE))

    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/atividades/records/ativ01",
                          callback=capture_patch, content_type="application/json")
    rsps_lib.add(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/q001",
                 status=204, body="")

    resp = client.post("/professor/questao/q001/excluir", data={"ativ_id": "ativ01"})
    assert resp.status_code in (200, 302)
    assert patch_body, "PATCH na atividade não foi feito"
    assert "q001" not in patch_body[0].get("questoes", [])


@rsps_lib.activate
def test_questao_form_get_retorna_200(client):
    """GET da nova questão exibe o formulário."""
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json=ATIVIDADE)
    resp = client.get("/professor/atividade/ativ01/questoes/nova")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Nova questão" in html
    assert "mc4" in html


@rsps_lib.activate
def test_editar_questao_get_retorna_200(client):
    """GET de edição exibe o formulário pré-preenchido."""
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001",
                 json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})
    resp = client.get("/professor/questao/q001/editar?ativ_id=ativ01")
    assert resp.status_code == 200
    assert "Qual é a função dos eritrócitos?" in resp.data.decode()
