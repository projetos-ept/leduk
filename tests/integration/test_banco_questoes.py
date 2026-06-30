"""Testes do banco de questões reutilizável por disciplina."""
import json

import responses as rsps_lib

from pb import PocketBaseClient

PB = "http://pb.test"

DISCIPLINA = {"id": "disc01", "nome": "Informática Aplicada"}
DISCIPLINAS = [
    {"id": "disc01", "nome": "Informática Aplicada"},
    {"id": "disc02", "nome": "Hematologia"},
]

Q_USADA = {
    "id": "q001", "tipo": "mc5", "enunciado": "Fases do LIS?", "peso": 2,
    "dificuldade": "medio", "assunto": "Fases do LIS", "disciplina": "disc01",
    "imagem": "", "feedback_geral": "",
}
Q_NAO_USADA = {
    "id": "q002", "tipo": "vf", "enunciado": "Conceitos gerais", "peso": 1,
    "dificuldade": "facil", "assunto": "Conceitos", "disciplina": "disc01",
    "imagem": "", "feedback_geral": "",
}

QUESTAO_MC = {
    "id": "q001", "tipo": "mc4", "enunciado": "Função dos eritrócitos?",
    "peso": 1, "dificuldade": "medio", "assunto": "Hemácias", "disciplina": "disc01",
    "feedback_geral": "", "imagem": "",
    "alternativas": [
        {"id": "a1", "letra": "A", "texto": "Transportar O₂", "correta": True, "feedback": ""},
        {"id": "a2", "letra": "B", "texto": "Infecções", "correta": False, "feedback": ""},
        {"id": "a3", "letra": "C", "texto": "Coagular", "correta": False, "feedback": ""},
        {"id": "a4", "letra": "D", "texto": "Anticorpos", "correta": False, "feedback": ""},
    ],
}

ATIVIDADE = {
    "id": "ativ01", "titulo": "Prova", "questoes": ["q001"],
    "turma": "turma01", "disciplina": "disc01", "ativa": False,
}


def _sess_prof(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok-prof"
        sess["role"] = "professor"
        sess["aluno_nome"] = "Prof. Ana"


# ── Banco lista todas as questões da disciplina ─────────────────────────────────

@rsps_lib.activate
def test_banco_lista_todas_questoes_inclui_nao_usadas(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01",
                 json=DISCIPLINA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records",
                 json={"items": [Q_USADA, Q_NAO_USADA]})
    # contar_uso: q001 usada em 1, q002 em 0 — mesma mock serve ambas; usa totalItems
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"totalItems": 1, "items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
                 json={"items": DISCIPLINAS})

    resp = client.get("/professor/disciplina/disc01/banco-questoes")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Fases do LIS?" in html
    assert "Conceitos gerais" in html  # questão não usada também aparece


# ── Filtro por assunto/tipo/dificuldade ─────────────────────────────────────────

@rsps_lib.activate
def test_banco_filtra_por_assunto_passa_filtro_na_query(client):
    _sess_prof(client)
    urls_questoes = []

    def cap_questoes(req):
        urls_questoes.append(req.url)
        return (200, {}, json.dumps({"items": [Q_USADA]}))

    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01",
                 json=DISCIPLINA)
    rsps_lib.add_callback(rsps_lib.GET, f"{PB}/api/collections/questoes/records",
                          callback=cap_questoes, content_type="application/json")
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"totalItems": 0, "items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
                 json={"items": DISCIPLINAS})

    resp = client.get("/professor/disciplina/disc01/banco-questoes?assunto=Fases+do+LIS")
    assert resp.status_code == 200
    assert any("assunto" in u for u in urls_questoes), \
        "o filtro de assunto não foi enviado na query"


# ── Clonar questão cria registro independente com alternativas duplicadas ────────

@rsps_lib.activate
def test_clonar_questao_duplica_alternativas(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001",
                 json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})

    questao_criada = []

    def cap_questao(req):
        questao_criada.append(json.loads(req.body))
        return (200, {}, json.dumps({"id": "qNOVA"}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/questoes/records",
                          callback=cap_questao, content_type="application/json")

    alts_criadas = []

    def cap_alt(req):
        alts_criadas.append(json.loads(req.body))
        return (200, {}, json.dumps({"id": f"alt{len(alts_criadas)}"}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/alternativas/records",
                          callback=cap_alt, content_type="application/json")

    resp = client.post("/professor/questao/q001/clonar")
    assert resp.status_code in (200, 302)
    assert questao_criada, "questão clonada não foi criada"
    assert "cópia" in questao_criada[0]["enunciado"]
    assert questao_criada[0]["disciplina"] == "disc01"
    assert len(alts_criadas) == 4, "alternativas não foram duplicadas"
    assert any(a["correta"] is True and a["letra"] == "A" for a in alts_criadas)


# ── Adicionar questão existente à atividade não duplica o registro ──────────────

@rsps_lib.activate
def test_adicionar_questoes_nao_duplica_no_array(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json=ATIVIDADE)

    patch_body = []

    def cap_patch(req):
        patch_body.append(json.loads(req.body))
        return (200, {}, json.dumps(ATIVIDADE))

    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/atividades/records/ativ01",
                          callback=cap_patch, content_type="application/json")

    # q001 já está na atividade; q002 é nova
    resp = client.post("/professor/atividade/ativ01/adicionar-questoes",
                       data={"questoes": ["q001", "q002"]})
    assert resp.status_code in (200, 302)
    assert patch_body, "atividade não foi atualizada"
    questoes = patch_body[0]["questoes"]
    assert questoes.count("q001") == 1, "questão existente foi duplicada"
    assert "q002" in questoes


# ── Reclassificar muda disciplina e assunto ─────────────────────────────────────

@rsps_lib.activate
def test_reclassificar_muda_disciplina_e_assunto(client):
    _sess_prof(client)
    patch_body = []

    def cap_patch(req):
        patch_body.append(json.loads(req.body))
        return (200, {}, json.dumps({"id": "q001"}))

    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/questoes/records/q001",
                          callback=cap_patch, content_type="application/json")

    resp = client.post("/professor/questao/q001/reclassificar",
                       data={"disciplina": "disc02", "assunto": "Novo assunto",
                             "origem_disciplina": "disc01"})
    assert resp.status_code in (200, 302)
    assert patch_body, "PATCH de reclassificação não foi feito"
    assert patch_body[0]["disciplina"] == "disc02"
    assert patch_body[0]["assunto"] == "Novo assunto"


# ── Excluir questão em uso limpa os vínculos órfãos ─────────────────────────────

@rsps_lib.activate
def test_excluir_questao_em_uso_limpa_vinculos_orfaos(client):
    _sess_prof(client)
    ativ_a = {"id": "ativA", "titulo": "Prova A", "questoes": ["q001", "q002"],
              "turma": "t1", "disciplina": "disc01"}
    ativ_b = {"id": "ativB", "titulo": "Prova B", "questoes": ["q003", "q001"],
              "turma": "t1", "disciplina": "disc01"}

    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": [ativ_a, ativ_b]})

    patch_a, patch_b = [], []

    def cap_a(req):
        patch_a.append(json.loads(req.body))
        return (200, {}, json.dumps(ativ_a))

    def cap_b(req):
        patch_b.append(json.loads(req.body))
        return (200, {}, json.dumps(ativ_b))

    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/atividades/records/ativA",
                          callback=cap_a, content_type="application/json")
    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/atividades/records/ativB",
                          callback=cap_b, content_type="application/json")
    rsps_lib.add(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/q001",
                 status=204, body="")

    resp = client.post("/professor/questao/q001/excluir",
                       data={"origem_disciplina": "disc01"})
    assert resp.status_code in (200, 302)
    # ambas as atividades foram atualizadas sem o ID removido, preservando as demais
    assert patch_a and patch_b, "nem todas as atividades em uso foram atualizadas"
    assert patch_a[0]["questoes"] == ["q002"]
    assert patch_b[0]["questoes"] == ["q003"]


# ── Contagem de uso reflete quantas atividades usam a questão ───────────────────

@rsps_lib.activate
def test_contar_uso_questao_retorna_total():
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"totalItems": 3, "items": []})
    pb = PocketBaseClient(PB, token="tok")
    assert pb.contar_uso_questao("q001") == 3


# ── Criar questão direto no banco (sem atividade) ──────────────────────────────

@rsps_lib.activate
def test_questao_nova_banco_vincula_disciplina(client):
    _sess_prof(client)
    questao_criada = []

    def cap_questao(req):
        questao_criada.append(json.loads(req.body))
        return (200, {}, json.dumps({"id": "qX"}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/questoes/records",
                          callback=cap_questao, content_type="application/json")
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/alternativas/records",
                 json={"id": "altX"})

    resp = client.post("/professor/disciplina/disc01/questao/nova", data={
        "tipo": "mc4",
        "enunciado": "Nova questão do banco",
        "peso": "2",
        "dificuldade": "medio",
        "assunto": "Tópico X",
        "correta": "A",
        "alt_texto_A": "Certa",
        "alt_texto_B": "Errada",
        "alt_texto_C": "Errada",
        "alt_texto_D": "Errada",
    })
    assert resp.status_code in (200, 302)
    assert questao_criada, "questão não foi criada no banco"
    assert questao_criada[0]["disciplina"] == "disc01"
    assert questao_criada[0]["assunto"] == "Tópico X"
    assert questao_criada[0]["tipo"] == "mc4"


@rsps_lib.activate
def test_questao_nova_banco_form_get_200(client):
    _sess_prof(client)
    resp = client.get("/professor/disciplina/disc01/questao/nova")
    assert resp.status_code == 200
    assert "Nova questão" in resp.data.decode()


# ── Seletor de questões da atividade ────────────────────────────────────────────

@rsps_lib.activate
def test_selecionar_questoes_exclui_ja_incluidas(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json=ATIVIDADE)  # já tem q001
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records",
                 json={"items": [Q_USADA, Q_NAO_USADA]})  # q001 e q002
    resp = client.get("/professor/atividade/ativ01/selecionar-questoes")
    assert resp.status_code == 200
    html = resp.data.decode()
    # q002 disponível para adicionar; q001 (já incluída) não aparece como opção
    assert "Conceitos gerais" in html
    assert "Fases do LIS?" not in html
