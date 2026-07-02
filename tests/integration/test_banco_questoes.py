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


@rsps_lib.activate
def test_banco_questoes_tem_checkboxes_selecao_em_massa(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=DISCIPLINA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records",
                 json={"items": [Q_USADA, Q_NAO_USADA]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"totalItems": 0, "items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": DISCIPLINAS})

    resp = client.get("/professor/disciplina/disc01/banco-questoes")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'class="seletor-check qb-select-check" value="q001"' in html
    assert 'class="seletor-check qb-select-check" value="q002"' in html
    assert "qb-select-all" in html
    assert "Excluir selecionadas" in html
    assert '/professor/disciplina/disc01/questoes/excluir-em-massa' in html


# ── Excluir em massa ─────────────────────────────────────────────────────────────

@rsps_lib.activate
def test_excluir_em_massa_remove_questoes_e_limpa_vinculos(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": [{"id": "ativ01", "questoes": ["q001", "q002"]}]})
    patch_cap = []
    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/atividades/records/ativ01",
                          callback=lambda r: (patch_cap.append(json.loads(r.body)), (200, {}, "{}"))[1],
                          content_type="application/json")
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": []})
    excluidas = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/q001",
                          callback=lambda r: (excluidas.append("q001"), (204, {}, ""))[1])
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/q002",
                          callback=lambda r: (excluidas.append("q002"), (204, {}, ""))[1])
    resp = client.post("/professor/disciplina/disc01/questoes/excluir-em-massa",
                       data={"questoes": ["q001", "q002"]})
    assert resp.status_code in (200, 302)
    assert set(excluidas) == {"q001", "q002"}
    # cascade: a atividade que usava q001 teve o vínculo removido
    assert patch_cap and "q001" not in patch_cap[0].get("questoes", [])


@rsps_lib.activate
def test_excluir_questao_remove_subitens_antes_da_questao(client):
    """Regressão: o PocketBase recusa (400) apagar uma questão enquanto ainda
    houver alternativas/itens_vf/pares referenciando-a via relation obrigatória
    sem cascadeDelete. A exclusão precisa apagar os subitens primeiro."""
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": [{"id": "a1"}, {"id": "a2"}]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/pares_associativos/records", json={"items": []})
    excluidas_alt = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/alternativas/records/a1",
                          callback=lambda r: (excluidas_alt.append("a1"), (204, {}, ""))[1])
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/alternativas/records/a2",
                          callback=lambda r: (excluidas_alt.append("a2"), (204, {}, ""))[1])
    excluida_questao = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/q001",
                          callback=lambda r: (excluida_questao.append("q001"), (204, {}, ""))[1])
    resp = client.post("/professor/questao/q001/excluir", data={"origem_disciplina": "disc01"})
    assert resp.status_code in (200, 302)
    assert set(excluidas_alt) == {"a1", "a2"}, "subitens deveriam ser removidos antes da questão"
    assert excluida_questao == ["q001"]


@rsps_lib.activate
def test_excluir_questao_400_persistente_nao_derruba_a_rota(client):
    """Se o PocketBase ainda recusar a exclusão (400) mesmo após remover
    vínculos e subitens, a rota não deve propagar a exceção (500) — deve
    redirecionar com um erro legível."""
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/pares_associativos/records", json={"items": []})
    rsps_lib.add(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/q001",
                 status=400, json={"code": 400, "message": "Failed to delete record."})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01",
                 json=DISCIPLINA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": DISCIPLINAS})
    resp = client.post("/professor/questao/q001/excluir", data={"origem_disciplina": "disc01"})
    assert resp.status_code in (200, 302)
    # segue o redirect e confirma que a página carrega com o aviso, sem 500
    if resp.status_code == 302:
        resp2 = client.get(resp.headers["Location"])
        assert resp2.status_code == 200
        assert "Não foi possível excluir" in resp2.data.decode()


@rsps_lib.activate
def test_excluir_em_massa_apaga_subitens_de_cada_questao(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": [{"id": "a1"}]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/pares_associativos/records", json={"items": []})
    rsps_lib.add(rsps_lib.DELETE, f"{PB}/api/collections/alternativas/records/a1", status=204, body="")
    rsps_lib.add(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/q001", status=204, body="")
    resp = client.post("/professor/disciplina/disc01/questoes/excluir-em-massa",
                       data={"questoes": ["q001"]})
    assert resp.status_code in (200, 302)


@rsps_lib.activate
def test_excluir_em_massa_reporta_falhas_sem_interromper(client):
    """Uma exclusão que falha persistentemente é contada em falhas_exclusao,
    mas não impede a exclusão das demais nem quebra a rota."""
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/pares_associativos/records", json={"items": []})
    rsps_lib.add(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/qRUIM",
                 status=400, json={"message": "Failed to delete record."})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/pares_associativos/records", json={"items": []})
    excluidas = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/qBOA",
                          callback=lambda r: (excluidas.append("qBOA"), (204, {}, ""))[1])
    resp = client.post("/professor/disciplina/disc01/questoes/excluir-em-massa",
                       data={"questoes": ["qRUIM", "qBOA"]})
    assert resp.status_code in (200, 302)
    assert excluidas == ["qBOA"], "a segunda exclusão deveria prosseguir mesmo após a primeira falhar"
    if resp.status_code == 302:
        assert "falhas_exclusao=1" in resp.headers["Location"]


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


# ── Multipart normaliza bool para "true"/"false" (evita rejeição do PocketBase) ──

@rsps_lib.activate
def test_criar_alternativa_com_imagem_envia_bool_como_string_minuscula():
    """requests faz str(False)=='False' em campos multipart; o parser de bool do
    PocketBase espera 'true'/'false'. Regressão: alternativas com imagem e
    correta=False sumiam/rejeitavam por causa dessa capitalização."""
    captured = {}

    def cap(r):
        captured["body"] = r.body if isinstance(r.body, bytes) else r.body.encode()
        return (200, {}, json.dumps({"id": "altX"}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/alternativas/records",
                          callback=cap, content_type="application/json")
    pb = PocketBaseClient(PB, token="tok")
    pb.criar_alternativa(
        {"questao": "q1", "letra": "B", "texto": "errada", "correta": False, "feedback": ""},
        ("img.png", b"fake-bytes", "image/png"),
    )
    body = captured["body"]
    assert b'name="correta"\r\n\r\nfalse' in body
    assert b'name="correta"\r\n\r\nFalse' not in body


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


# ── Excluir questão com tentativas vinculadas ────────────────────────────────

@rsps_lib.activate
def test_excluir_questao_com_tentativas_desvincula_sem_deletar(client):
    """Regressão: quando há tentativas vinculadas à questão via campo `questao`,
    o PocketBase recusa (400) a exclusão. A solução é anular o campo `questao`
    nas tentativas (preservando o histórico) antes de excluir a questão."""
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/pares_associativos/records", json={"items": []})
    # tentativas vinculadas à questão
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"items": [{"id": "tent01"}, {"id": "tent02"}]})

    patched = []
    deleted_tentativas = []

    def cap_patch(req):
        patched.append(req.url)
        return (200, {}, json.dumps({"id": req.url.split("/")[-1]}))

    def cap_delete_tentativa(req):
        deleted_tentativas.append(req.url)
        return (204, {}, "")

    rsps_lib.add_callback(rsps_lib.PATCH,
                          f"{PB}/api/collections/tentativas/records/tent01",
                          callback=cap_patch, content_type="application/json")
    rsps_lib.add_callback(rsps_lib.PATCH,
                          f"{PB}/api/collections/tentativas/records/tent02",
                          callback=cap_patch, content_type="application/json")
    rsps_lib.add_callback(rsps_lib.DELETE,
                          f"{PB}/api/collections/tentativas/records/tent01",
                          callback=cap_delete_tentativa, content_type="application/json")
    rsps_lib.add_callback(rsps_lib.DELETE,
                          f"{PB}/api/collections/tentativas/records/tent02",
                          callback=cap_delete_tentativa, content_type="application/json")
    rsps_lib.add(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/q001",
                 status=204, body="")

    resp = client.post("/professor/questao/q001/excluir", data={"origem_disciplina": "disc01"})
    assert resp.status_code in (200, 302)
    # tentativas foram desvinculadas (PATCH), não deletadas (DELETE)
    assert len(patched) == 2, "as duas tentativas deveriam ter sido desvinculadas via PATCH"
    assert len(deleted_tentativas) == 0, "tentativas não devem ser deletadas — são histórico"


@rsps_lib.activate
def test_excluir_questao_sem_tentativas_funciona_normalmente(client):
    """Sem tentativas vinculadas a exclusão segue o fluxo normal."""
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/pares_associativos/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records", json={"items": []})
    rsps_lib.add(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/q001",
                 status=204, body="")

    resp = client.post("/professor/questao/q001/excluir", data={"origem_disciplina": "disc01"})
    assert resp.status_code in (200, 302)


@rsps_lib.activate
def test_tentativas_com_questao_null_nao_quebram_historico(client):
    """Tentativas com questao=null não devem causar erro no histórico do aluno.
    A rota de resultado (/htmx/resultado) usa apenas os dados da sessão
    (respostas), não busca tentativas pelo campo questao — null no PocketBase
    não afeta o placar exibido."""
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01",
                 json={"id": "ativ01", "exibir_feedback_pos": False, "nota_automatica": False})
    with client.session_transaction() as sess:
        sess["modo_prova"] = False
        sess["respostas"] = [{"score_raw": 1, "score_max": 1, "correta": True, "_peso": 1, "_num": 1}]
        sess["tentativa_id"] = "tent01"
        sess["nota_automatica"] = False
        sess["tentativa_concluida"] = True
        sess["max_tentativas"] = 0
    resp = client.get("/htmx/resultado/ativ01")
    assert resp.status_code == 200
    # a página de placar renderiza normalmente — questao=null no PocketBase não causa erro
    assert "placar-card" in resp.data.decode()
