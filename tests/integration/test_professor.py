"""Testes de integração para o módulo de correção do professor."""
import json

import responses as rsps_lib

PB = "http://pb.test"

ATIVIDADE = {
    "id": "ativ01",
    "titulo": "Prova Hematologia",
    "questoes": ["q001", "q002"],
    "ativa": True,
    "disponivel_de": None,
    "disponivel_ate": None,
    "tempo_limite": 0,
    "disciplina": "disc01",
    "max_tentativas": 1,
    "nota_automatica": False,
    "exibir_feedback_pos": True,
    "valor_total": 3.0,
}

TENTATIVA_SEM_NOTA = {
    "id": "tent01",
    "disciplina": "ativ01",
    "aluno_id": "aluno01",
    "aluno_nome": "Lucas",
    "numero_tentativa": 1,
    "concluida": True,
    "nota_liberada": False,
    "score_raw": 0,
    "score_max": 0,
    "score_percentual": 0,
}

QUESTAO_ABERTA = {
    "id": "q001",
    "tipo": "aberta",
    "enunciado": "Explique a função dos eritrócitos.",
    "peso": 2,
}

QUESTAO_MC = {
    "id": "q002",
    "tipo": "mc4",
    "enunciado": "Qual é a função dos eritrócitos?",
    "peso": 3,
    "alternativas": [
        {"id": "a1", "letra": "A", "texto": "Transportar oxigênio", "correta": True},
        {"id": "a2", "letra": "B", "texto": "Combater infecções", "correta": False},
        {"id": "a3", "letra": "C", "texto": "Coagular sangue", "correta": False},
        {"id": "a4", "letra": "D", "texto": "Produzir anticorpos", "correta": False},
    ],
}

RESPOSTA_ABERTA = {
    "id": "resp01",
    "questao": "q001",
    "tentativa_id": "tent01",
    "tipo_questao": "aberta",
    "texto_resposta": "Eritrócitos transportam oxigênio pelo sangue.",
    "score_raw": None,
    "score_max": None,
    "comentario_professor": None,
}

RESPOSTA_MC = {
    "id": "resp02",
    "questao": "q002",
    "tentativa_id": "tent01",
    "tipo_questao": "mc4",
    "score_raw": 1,
    "score_max": 1,
    "correta": True,
}


# ── Rota /professor/atividade/<id>/notas-abertas ──────────────────────────────

@rsps_lib.activate
def test_notas_abertas_retorna_200(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["aluno_nome"] = "Professor"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json=ATIVIDADE)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_SEM_NOTA]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [RESPOSTA_ABERTA, RESPOSTA_MC]})  # listar_respostas_tentativa
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001",
                 json=QUESTAO_ABERTA)
    resp = client.get("/professor/atividade/ativ01/notas-abertas")
    assert resp.status_code == 200


@rsps_lib.activate
def test_notas_abertas_exibe_resposta_aluno(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["aluno_nome"] = "Professor"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json=ATIVIDADE)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_SEM_NOTA]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [RESPOSTA_ABERTA, RESPOSTA_MC]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001",
                 json=QUESTAO_ABERTA)
    resp = client.get("/professor/atividade/ativ01/notas-abertas")
    html = resp.data.decode()
    assert "Lucas" in html
    assert "Eritrócitos transportam oxigênio pelo sangue." in html
    assert "Explique a função dos eritrócitos." in html


@rsps_lib.activate
def test_notas_abertas_sem_pendencias(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json=ATIVIDADE)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": []})
    resp = client.get("/professor/atividade/ativ01/notas-abertas")
    assert resp.status_code == 200
    assert "Nenhuma tentativa aguardando correção" in resp.data.decode()


# ── Rota /professor/questao-aberta/<id>/avaliar ───────────────────────────────

@rsps_lib.activate
def test_avaliar_redireciona_para_notas_abertas(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok"
    # listar_respostas_tentativa
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [RESPOSTA_ABERTA, RESPOSTA_MC]})
    # buscar_questao para a resposta aberta
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001",
                 json=QUESTAO_ABERTA)
    # avaliar_questao_aberta PATCH
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/tentativas/records/resp01",
                 json={**RESPOSTA_ABERTA, "score_raw": 1.5, "score_max": 2.0})
    # buscar_atividade para recalcular nota_final
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json=ATIVIDADE)
    # listar_respostas_tentativa novamente (respostas atualizadas)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [
                     {**RESPOSTA_ABERTA, "score_raw": 1.5, "score_max": 2.0},
                     RESPOSTA_MC,
                 ]})
    # buscar_questao para calcular pesos
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001",
                 json=QUESTAO_ABERTA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q002",
                 json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})
    # patch_tentativa_nota_final
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/tentativas/records/tent01",
                 json={**TENTATIVA_SEM_NOTA, "nota_final": 2.7})
    # liberar_nota
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/tentativas/records/tent01",
                 json={**TENTATIVA_SEM_NOTA, "nota_liberada": True})
    # tentativas para a rota de redirect (notas_abertas re-fetch)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json=ATIVIDADE)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": []})

    resp = client.post(
        "/professor/questao-aberta/tent01/avaliar",
        data={"ativ_id": "ativ01", "nota_resp01": "1.5"},
    )
    assert resp.status_code in (200, 302)


# ── Bloco 2 tests ────────────────────────────────────────────────────────────

TURMA = {"id": "turma01", "nome": "1º Ano EMI", "modalidade": "EMI", "ano": "2025"}

def test_aluno_nao_acessa_dashboard(client):
    """Aluno com role='aluno' é redirecionado para home."""
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["role"] = "aluno"
    resp = client.get("/professor/dashboard")
    assert resp.status_code == 302
    assert resp.location.endswith("/") or "/" in resp.location

@rsps_lib.activate
def test_professor_acessa_dashboard(client):
    """Professor vê turmas no dashboard."""
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["role"] = "professor"
        sess["aluno_nome"] = "Prof. Ana"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records",
                 json={"items": [TURMA]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": [ATIVIDADE]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": []})
    resp = client.get("/professor/dashboard")
    assert resp.status_code == 200
    assert "1º Ano EMI" in resp.data.decode()

@rsps_lib.activate
def test_toggle_desativa_atividade(client):
    """Toggle muda ativa=True para False e retorna fragmento HTML."""
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["role"] = "professor"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={**ATIVIDADE, "ativa": True})
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/atividades/records/ativ01",
                 json={**ATIVIDADE, "ativa": False})
    resp = client.post("/professor/atividade/ativ01/toggle-ativa")
    assert resp.status_code == 200
    assert "toggle-off" in resp.data.decode() or "Inativa" in resp.data.decode()

@rsps_lib.activate
def test_liberar_notas_em_lote(client):
    """Liberar em lote chama liberar_nota para cada tentativa selecionada."""
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["role"] = "professor"
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/tentativas/records/tent01",
                 json={"id": "tent01", "nota_liberada": True})
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/tentativas/records/tent02",
                 json={"id": "tent02", "nota_liberada": True})
    # redirect target: professor_notas
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json=ATIVIDADE)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": []})
    resp = client.post("/professor/atividade/ativ01/liberar-notas",
                       data={"tentativa_ids": ["tent01", "tent02"]})
    assert resp.status_code in (200, 302)


# ── Datas de disponibilidade ─────────────────────────────────────────────────

DISCIPLINAS = [{"id": "disc01", "nome": "Hematologia"}]
TURMAS_LISTA = [{"id": "turma01", "nome": "1º EMI"}]


@rsps_lib.activate
def test_criar_atividade_sem_datas_aceita(client):
    """Criar atividade sem datas de disponibilidade envia None e PocketBase aceita."""
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["role"] = "professor"

    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records",
                 json={"items": TURMAS_LISTA})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
                 json={"items": DISCIPLINAS})

    captured = []

    def capture(req):
        captured.append(json.loads(req.body))
        return (200, {}, json.dumps({"id": "ativ_new", **json.loads(req.body)}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/atividades/records",
                          callback=capture, content_type="application/json")

    resp = client.post("/professor/atividade/nova", data={
        "titulo": "Prova Hematologia",
        "turma": "turma01",
        "disciplina": "disc01",
        "max_tentativas": "1",
        "tempo_limite": "0",
    })
    assert resp.status_code in (200, 302)
    assert captured, "POST para PocketBase não foi feito"
    assert captured[0]["disponivel_de"] is None
    assert captured[0]["disponivel_ate"] is None


@rsps_lib.activate
def test_criar_atividade_com_datas_formato_pb(client):
    """Criar atividade com datas converte para formato ISO aceito pelo PocketBase."""
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["role"] = "professor"

    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records",
                 json={"items": TURMAS_LISTA})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
                 json={"items": DISCIPLINAS})

    captured = []

    def capture(req):
        captured.append(json.loads(req.body))
        return (200, {}, json.dumps({"id": "ativ_new", **json.loads(req.body)}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/atividades/records",
                          callback=capture, content_type="application/json")

    resp = client.post("/professor/atividade/nova", data={
        "titulo": "Prova Hematologia",
        "turma": "turma01",
        "disciplina": "disc01",
        "max_tentativas": "1",
        "tempo_limite": "0",
        "disponivel_de": "2026-06-29T08:00",
        "disponivel_ate": "2026-07-31T23:59",
    })
    assert resp.status_code in (200, 302)
    assert captured, "POST para PocketBase não foi feito"
    assert captured[0]["disponivel_de"] == "2026-06-29 08:00:00.000Z"
    assert captured[0]["disponivel_ate"] == "2026-07-31 23:59:00.000Z"


# ── Token JWT nas chamadas autenticadas ───────────────────────────────────────

@rsps_lib.activate
def test_criar_atividade_envia_token_authorization(client):
    """Criar atividade envia o JWT da sessão no header Authorization."""
    with client.session_transaction() as sess:
        sess["token"] = "jwt-do-professor-xyz"
        sess["role"] = "professor"

    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records",
                 json={"items": TURMAS_LISTA})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
                 json={"items": DISCIPLINAS})

    captured_headers = []

    def capture(req):
        captured_headers.append(dict(req.headers))
        return (200, {}, json.dumps({"id": "ativ_new"}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/atividades/records",
                          callback=capture, content_type="application/json")

    client.post("/professor/atividade/nova", data={
        "titulo": "Prova Hematologia",
        "turma": "turma01",
        "disciplina": "disc01",
        "max_tentativas": "1",
        "tempo_limite": "0",
    })

    assert captured_headers, "POST para PocketBase não foi feito"
    auth = captured_headers[0].get("Authorization", "")
    assert auth == "jwt-do-professor-xyz", (
        f"Token não enviado ou errado no header Authorization: {auth!r}"
    )
