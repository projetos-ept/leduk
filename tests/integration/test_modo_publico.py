"""Testes de integração do modo público de atividades (turmas públicas sem matrícula)."""
import json

import responses as rsps_lib

PB = "http://pb.test"

TURMA_PUBLICA = {"id": "turma01", "nome": "Curso Aberto", "modalidade": "Aberta",
                 "ano": "2026", "publica": True, "ativa": True,
                 "descricao": "Turma aberta ao público."}
TURMA_PRIVADA = {"id": "turma02", "nome": "1º EMI", "modalidade": "EMI",
                 "ano": "2026", "publica": False, "ativa": True}
DISCIPLINA = {"id": "disc01", "nome": "Hematologia"}
ATIVIDADE = {
    "id": "ativ01",
    "titulo": "Quiz Aberto",
    "questoes": ["q001"],
    "ativa": True,
    "turma": "turma01",
    "disciplina": "disc01",
    "disponivel_de": None,
    "disponivel_ate": None,
    "tempo_limite": 0,
    "max_tentativas": 2,
    "nota_automatica": True,
    "exibir_feedback_pos": True,
    "modo_prova": False,
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
TENTATIVA_PUBLICA = {
    "id": "tp1", "atividade": "ativ01", "aluno_id": "",
    "aluno_nome": "Visitante Silva", "aluno_email": "visitante@example.com",
    "aluno_turma": "3º B", "numero_tentativa": 1, "concluida": True,
    "nota_liberada": True, "score_percentual": 80, "nota_final": None,
    "created": "2026-07-01T14:30:00Z",
}


def _mock_atividade_publica():
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA_PUBLICA)


# ── Página pública ────────────────────────────────────────────────────────────

@rsps_lib.activate
def test_pagina_publica_200_sem_login(client):
    _mock_atividade_publica()
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=DISCIPLINA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turma_materiais/records", json={"items": []})
    resp = client.get("/publica/ativ01")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Quiz Aberto" in html
    assert "Responder atividade" in html


@rsps_lib.activate
def test_pagina_publica_404_turma_nao_publica(client):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={**ATIVIDADE, "turma": "turma02"})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma02", json=TURMA_PRIVADA)
    resp = client.get("/publica/ativ01")
    assert resp.status_code == 404


# ── Identificação ─────────────────────────────────────────────────────────────

@rsps_lib.activate
def test_identificar_email_novo_inicia_fluxo(client):
    _mock_atividade_publica()
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records", json={"items": []})
    resp = client.post("/publica/ativ01/identificar",
                       data={"nome": "Visitante Silva", "email": "Novo@Example.com", "turma": "3º B"})
    assert resp.status_code == 302
    assert "/atividade/ativ01" in resp.headers["Location"]
    with client.session_transaction() as sess:
        assert sess["pub_modo"] is True
        assert sess["pub_nome"] == "Visitante Silva"
        assert sess["pub_email"] == "novo@example.com"  # normalizado
        assert sess["pub_turma"] == "3º B"
        assert sess["pub_ativ_id"] == "ativ01"


@rsps_lib.activate
def test_identificar_email_repetido_pede_confirmacao(client):
    _mock_atividade_publica()
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_PUBLICA]})
    resp = client.post("/publica/ativ01/identificar",
                       data={"nome": "Visitante Silva", "email": "visitante@example.com"})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "já respondeu 1 vez" in html
    assert "tentar novamente" in html.lower()
    with client.session_transaction() as sess:
        assert not sess.get("pub_modo")


@rsps_lib.activate
def test_identificar_com_confirmacao_prossegue(client):
    _mock_atividade_publica()
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_PUBLICA]})
    resp = client.post("/publica/ativ01/identificar",
                       data={"nome": "Visitante Silva", "email": "visitante@example.com",
                             "confirmar": "1"})
    assert resp.status_code == 302
    assert "/atividade/ativ01" in resp.headers["Location"]


@rsps_lib.activate
def test_identificar_limite_atingido(client):
    _mock_atividade_publica()
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_PUBLICA, {**TENTATIVA_PUBLICA, "id": "tp2"}]})
    resp = client.post("/publica/ativ01/identificar",
                       data={"nome": "Visitante Silva", "email": "visitante@example.com"})
    assert resp.status_code == 403
    assert "Limite de 2 tentativas atingido" in resp.data.decode()


@rsps_lib.activate
def test_identificar_sem_nome_ou_email_422(client):
    _mock_atividade_publica()
    resp = client.post("/publica/ativ01/identificar", data={"nome": "", "email": ""})
    assert resp.status_code == 422


# ── Fluxo de resposta público ─────────────────────────────────────────────────

def _sessao_publica(client):
    with client.session_transaction() as sess:
        sess["pub_modo"] = True
        sess["pub_nome"] = "Visitante Silva"
        sess["pub_email"] = "visitante@example.com"
        sess["pub_turma"] = "3º B"
        sess["pub_ativ_id"] = "ativ01"
        sess["ativ_id"] = "ativ01"
        sess["fila"] = []
        sess["total"] = 1
        sess["respostas"] = []
        sess["tentativa_id"] = "tent-pub"
        sess["nota_automatica"] = True
        sess["max_tentativas"] = 2


@rsps_lib.activate
def test_responder_publico_grava_sem_aluno_id(client):
    _sessao_publica(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001", json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})

    captured = []

    def capture(request):
        body = json.loads(request.body)
        captured.append(body)
        return (200, {}, json.dumps({"id": "resp1", **body}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/tentativas/records",
                          callback=capture, content_type="application/json")
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/tentativas/records/tent-pub",
                 json={"id": "tent-pub"})

    resp = client.post("/htmx/responder", data={"tipo": "mc4", "questao_id": "q001", "resposta": "A"})
    assert resp.status_code == 200
    assert captured, "registrar_tentativa não foi chamado"
    body = captured[0]
    assert body["aluno_id"] == ""
    assert body["aluno_nome"] == "Visitante Silva"
    assert body["aluno_email"] == "visitante@example.com"
    assert body["aluno_turma"] == "3º B"


@rsps_lib.activate
def test_atividade_cria_tentativa_publica_com_extras(client):
    with client.session_transaction() as sess:
        sess["pub_modo"] = True
        sess["pub_nome"] = "Visitante Silva"
        sess["pub_email"] = "visitante@example.com"
        sess["pub_turma"] = "3º B"
        sess["pub_ativ_id"] = "ativ01"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    # contar_tentativas_por_email → 0 usadas
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records", json={"items": []})

    captured = []

    def capture(request):
        body = json.loads(request.body)
        captured.append(body)
        return (200, {}, json.dumps({"id": "tent-nova", **body}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/tentativas/records",
                          callback=capture, content_type="application/json")

    resp = client.get("/atividade/ativ01")
    assert resp.status_code == 200
    assert captured
    body = captured[0]
    assert body["aluno_id"] == ""
    assert body["aluno_email"] == "visitante@example.com"
    assert body["aluno_turma"] == "3º B"


@rsps_lib.activate
def test_aluno_logado_fluxo_normal_nao_afetado(client):
    """Aluno com conta e sem pub_modo: tentativa criada com aluno_id normal."""
    with client.session_transaction() as sess:
        sess["token"] = "tok"
        sess["aluno_id"] = "aluno01"
        sess["aluno_nome"] = "Maria"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={**ATIVIDADE, "max_tentativas": 0})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records", json={"items": []})

    captured = []

    def capture(request):
        body = json.loads(request.body)
        captured.append(body)
        return (200, {}, json.dumps({"id": "tent-n", **body}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/tentativas/records",
                          callback=capture, content_type="application/json")

    resp = client.get("/atividade/ativ01")
    assert resp.status_code == 200
    assert captured
    assert captured[0]["aluno_id"] == "aluno01"
    assert "aluno_email" not in captured[0]


# ── Gestão do professor ───────────────────────────────────────────────────────

def _sessao_professor(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok-prof"
        sess["aluno_id"] = "prof01"
        sess["aluno_nome"] = "Prof"
        sess["role"] = "professor"


@rsps_lib.activate
def test_professor_publico_lista_turmas_publicas(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records",
                 json={"items": [TURMA_PUBLICA]})
    resp = client.get("/professor/publico")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Curso Aberto" in html


@rsps_lib.activate
def test_professor_publico_turma_nova_cria_publica(client):
    _sessao_professor(client)
    captured = []

    def capture(request):
        body = json.loads(request.body)
        captured.append(body)
        return (200, {}, json.dumps({"id": "turma-nova", **body}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/turmas/records",
                          callback=capture, content_type="application/json")
    resp = client.post("/professor/publico/turma/nova",
                       data={"nome": "Nova Aberta", "modalidade": "Aberta", "ano": "2026",
                             "descricao": "Descrição"})
    assert resp.status_code == 302
    assert captured
    assert captured[0]["publica"] is True
    assert captured[0]["ativa"] is True


@rsps_lib.activate
def test_respostas_publicas_lista_respondentes(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_PUBLICA]})
    resp = client.get("/professor/atividade/ativ01/respostas-publicas")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Visitante Silva" in html
    assert "visitante@example.com" in html
    assert "3º B" in html


@rsps_lib.activate
def test_respostas_publicas_csv(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_PUBLICA]})
    resp = client.get("/professor/atividade/ativ01/respostas-publicas.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["Content-Type"]
    corpo = resp.data.decode()
    assert "visitante@example.com" in corpo
    assert "Visitante Silva" in corpo


@rsps_lib.activate
def test_relatorio_publico_geral_responde(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=DISCIPLINA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_PUBLICA]})
    resp = client.get("/professor/atividade/ativ01/relatorio-publico")
    assert resp.status_code == 200


@rsps_lib.activate
def test_relatorio_publico_individual_mostra_detalhamento(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=DISCIPLINA)
    # listar_tentativas_publicas_por_email
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_PUBLICA]})
    # _montar_questoes_revisao → listar_respostas_tentativa
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [{"id": "r1", "questao": "q001", "correta": True,
                                  "resposta_dada": "A", "score_raw": 1, "score_max": 1,
                                  "tipo_questao": "mc4"}]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001", json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})
    resp = client.get("/professor/atividade/ativ01/relatorio-publico/visitante@example.com")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Questão 1" in html
    assert "Correta" in html
    assert "Qual alternativa correta?" in html
    assert "resposta assinalada" in html


QUESTAO_VF = {
    "id": "q002",
    "tipo": "vf",
    "enunciado": "Julgue as afirmações",
    "peso": 1,
    "itens_vf": [
        {"id": "vf1", "ordem": 1, "afirmacao": "O sangue é vermelho", "gabarito": True},
        {"id": "vf2", "ordem": 2, "afirmacao": "Leucócitos são hemácias", "gabarito": False},
    ],
}


@rsps_lib.activate
def test_relatorio_publico_individual_mostra_gabarito_vf(client):
    """Bug relatado: comprovante não mostrava resposta do aluno nem gabarito
    para questões V/F — resposta_dada é str(dict), não uma letra simples."""
    _sessao_professor(client)
    ativ_vf = {**ATIVIDADE, "questoes": ["q002"]}
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ativ_vf)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=DISCIPLINA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_PUBLICA]})
    # aluno marcou item 1 certo (True) e item 2 errado (marcou True, gabarito é False)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [{"id": "r1", "questao": "q002", "correta": False,
                                  "resposta_dada": "{'1': True, '2': True}",
                                  "score_raw": 1, "score_max": 2, "tipo_questao": "vf"}]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q002", json=QUESTAO_VF)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records",
                 json={"items": QUESTAO_VF["itens_vf"]})
    resp = client.get("/professor/atividade/ativ01/relatorio-publico/visitante@example.com")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "O sangue é vermelho" in html
    assert "Leucócitos são hemácias" in html
    # item 2: aluno respondeu Verdadeiro mas gabarito é Falso — ambos precisam aparecer
    assert "Falso" in html  # gabarito do item 2
    assert "Verdadeiro" in html  # resposta do aluno no item 2


QUESTAO_ASSOC = {
    "id": "q003",
    "tipo": "associativa",
    "enunciado": "Associe as colunas",
    "peso": 1,
    "pares_associativos": [
        {"id": "p1", "ordem": 1, "coluna_a": "Hemácia", "coluna_b": "Transporte de O2"},
        {"id": "p2", "ordem": 2, "coluna_a": "Leucócito", "coluna_b": "Defesa"},
    ],
}


@rsps_lib.activate
def test_relatorio_publico_individual_mostra_gabarito_associativa(client):
    _sessao_professor(client)
    ativ_assoc = {**ATIVIDADE, "questoes": ["q003"]}
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ativ_assoc)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=DISCIPLINA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_PUBLICA]})
    # aluno errou o par 2 (associou Leucócito com "Transporte de O2" em vez de "Defesa")
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [{"id": "r1", "questao": "q003", "correta": False,
                                  "resposta_dada": "{'1': 'Transporte de O2', '2': 'Transporte de O2'}",
                                  "score_raw": 1, "score_max": 2, "tipo_questao": "associativa"}]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q003", json=QUESTAO_ASSOC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/pares_associativos/records",
                 json={"items": QUESTAO_ASSOC["pares_associativos"]})
    resp = client.get("/professor/atividade/ativ01/relatorio-publico/visitante@example.com")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Hemácia" in html
    assert "Leucócito" in html
    assert "Defesa" in html  # gabarito correto do par errado precisa aparecer
    assert "Transporte de O2" in html  # resposta (errada) do aluno para esse par
    # par 1 (Hemácia) foi acertado — a coluna "Correta" deve mostrar o gabarito
    # mesmo assim, não só nos pares errados (bug relatado: só aparecia nos errados)
    assert html.count("Transporte de O2") == 3


@rsps_lib.activate
def test_relatorio_publico_individual_mostra_detalhamento_mesmo_em_modo_prova(client):
    """Este relatório é a devolutiva que o PROFESSOR gera manualmente para
    entregar ao aluno — modo_prova regula o que o aluno vê sozinho durante a
    prova, não deve esconder o detalhamento do professor aqui."""
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={**ATIVIDADE, "modo_prova": True})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=DISCIPLINA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_PUBLICA]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [{"id": "r1", "questao": "q001", "correta": True,
                                  "resposta_dada": "A", "score_raw": 1, "score_max": 1,
                                  "tipo_questao": "mc4"}]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001", json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})
    resp = client.get("/professor/atividade/ativ01/relatorio-publico/visitante@example.com")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Qual alternativa correta?" in html
    assert "modo prova" not in html.lower()


@rsps_lib.activate
def test_relatorio_publico_individual_multiplas_tentativas_com_quebra_pagina(client):
    _sessao_professor(client)
    segunda = {**TENTATIVA_PUBLICA, "id": "tp2", "numero_tentativa": 2,
               "created": "2026-07-02T10:00:00Z"}
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=DISCIPLINA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [TENTATIVA_PUBLICA, segunda]})
    # respostas para cada uma das 2 tentativas
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records", json={"items": []})
    resp = client.get("/professor/atividade/ativ01/relatorio-publico/visitante@example.com")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Tentativa 1" in html
    assert "Tentativa 2" in html
    assert "page-break-before" in html  # CSS de impressão presente


@rsps_lib.activate
def test_placar_publico_nao_exibe_tentativas_restantes(client):
    _sessao_publica(client)
    # fila vazia → placar; concluir_tentativa PATCH
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/tentativas/records/tent-pub",
                 json={"id": "tent-pub"})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    resp = client.get("/htmx/proxima/ativ01")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "placar" in html
    # público não vê badge de tentativas restantes
    assert "restante" not in html


@rsps_lib.activate
def test_criar_tentativa_publica_fallback_sem_extras(client):
    """PB sem os campos aluno_email/aluno_turma (migração pendente):
    primeiro POST falha, retry sem extras cria o registro."""
    with client.session_transaction() as sess:
        sess["pub_modo"] = True
        sess["pub_nome"] = "Visitante Silva"
        sess["pub_email"] = "visitante@example.com"
        sess["pub_turma"] = "3º B"
        sess["pub_ativ_id"] = "ativ01"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records", json={"items": []})

    captured = []

    def capture(request):
        body = json.loads(request.body)
        captured.append(body)
        if "aluno_email" in body:
            return (400, {}, json.dumps({"message": "Failed to create record."}))
        return (200, {}, json.dumps({"id": "tent-fb", **body}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/tentativas/records",
                          callback=capture, content_type="application/json")

    resp = client.get("/atividade/ativ01")
    assert resp.status_code == 200
    assert len(captured) == 2, "deveria tentar com extras e refazer sem"
    assert "aluno_email" in captured[0]
    assert "aluno_email" not in captured[1]
    with client.session_transaction() as sess:
        assert sess["tentativa_id"] == "tent-fb"


@rsps_lib.activate
def test_responder_publico_fallback_sem_campos_publicos(client):
    """Resposta pública não se perde quando PB rejeita aluno_email."""
    _sessao_publica(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001", json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})

    captured = []

    def capture(request):
        body = json.loads(request.body)
        captured.append(body)
        if "aluno_email" in body:
            return (400, {}, json.dumps({"message": "Failed to create record."}))
        return (200, {}, json.dumps({"id": "resp-fb", **body}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/tentativas/records",
                          callback=capture, content_type="application/json")
    rsps_lib.add(rsps_lib.PATCH, f"{PB}/api/collections/tentativas/records/tent-pub",
                 json={"id": "tent-pub"})

    resp = client.post("/htmx/responder", data={"tipo": "mc4", "questao_id": "q001", "resposta": "A"})
    assert resp.status_code == 200
    assert len(captured) == 2
    assert "aluno_email" not in captured[1]
    assert captured[1]["aluno_nome"] == "Visitante Silva"  # identidade preservada
