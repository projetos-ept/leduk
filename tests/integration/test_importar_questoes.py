"""Importação de questões via JSON (colar ou arquivo), com imagens link/base64."""
import io
import json

import responses as rsps_lib

PB = "http://pb.test"
DISCIPLINA = {"id": "disc01", "nome": "Informática Aplicada"}

# 1x1 PNG transparente
PNG_B64 = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
           "AAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def _sess_prof(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok-prof"
        sess["role"] = "professor"
        sess["aluno_nome"] = "Lucas"


def _mock_disc():
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=DISCIPLINA)


@rsps_lib.activate
def test_importar_form_get_200(client):
    _sess_prof(client)
    _mock_disc()
    resp = client.get("/professor/disciplina/disc01/importar-questoes")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Importar questões" in html
    assert "/static/exemplos/questoes_exemplo.json" in html


@rsps_lib.activate
def test_importar_todos_os_tipos_via_colar(client):
    _sess_prof(client)
    _mock_disc()
    questoes_criadas = []

    def cap_q(r):
        body = json.loads(r.body)
        questoes_criadas.append(body)
        return (200, {}, json.dumps({"id": f"q{len(questoes_criadas)}"}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/questoes/records",
                          callback=cap_q, content_type="application/json")
    alts = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/alternativas/records",
                          callback=lambda r: (alts.append(json.loads(r.body)), (200, {}, json.dumps({"id": "a"})))[1],
                          content_type="application/json")
    itens = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/itens_vf/records",
                          callback=lambda r: (itens.append(json.loads(r.body)), (200, {}, json.dumps({"id": "i"})))[1],
                          content_type="application/json")
    pares = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/pares_associativos/records",
                          callback=lambda r: (pares.append(json.loads(r.body)), (200, {}, json.dumps({"id": "p"})))[1],
                          content_type="application/json")

    payload = {"questoes": [
        {"tipo": "mc4", "enunciado": "MC4?", "alternativas": [
            {"letra": "A", "texto": "certa", "correta": True},
            {"letra": "B", "texto": "errada", "correta": False}]},
        {"tipo": "vf", "enunciado": "VF?", "itens_vf": [
            {"afirmacao": "a", "correta": True}, {"afirmacao": "b", "correta": False}]},
        {"tipo": "associativa", "enunciado": "Assoc?", "pares": [
            {"coluna_a": "x", "coluna_b": "y"}]},
        {"tipo": "aberta", "enunciado": "Disserte."},
    ]}
    resp = client.post("/professor/disciplina/disc01/importar-questoes",
                       data={"acao": "importar", "json_text": json.dumps(payload)})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "4 de 4" in html
    assert len(questoes_criadas) == 4
    tipos = {q["tipo"] for q in questoes_criadas}
    assert tipos == {"mc4", "vf", "associativa", "aberta"}
    assert len(alts) == 2 and len(itens) == 2 and len(pares) == 1
    # disciplina aplicada a todas
    assert all(q["disciplina"] == "disc01" for q in questoes_criadas)


@rsps_lib.activate
def test_importar_via_arquivo_json(client):
    _sess_prof(client)
    _mock_disc()
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/questoes/records", json={"id": "q1"})
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/alternativas/records", json={"id": "a1"})
    payload = json.dumps([{"tipo": "mc4", "enunciado": "Via arquivo?",
                           "alternativas": [{"letra": "A", "texto": "ok", "correta": True}]}])
    data = {"acao": "importar",
            "json_file": (io.BytesIO(payload.encode("utf-8")), "questoes.json")}
    resp = client.post("/professor/disciplina/disc01/importar-questoes",
                       data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert "1 de 1" in resp.data.decode()


@rsps_lib.activate
def test_importar_imagem_base64_faz_upload_multipart(client):
    _sess_prof(client)
    _mock_disc()
    captured = {}

    def cap(r):
        # multipart: corpo contém o nome do campo de arquivo "imagem"
        captured["ctype"] = r.headers.get("Content-Type", "")
        captured["has_file"] = b"name=\"imagem\"" in (r.body if isinstance(r.body, bytes) else r.body.encode())
        return (200, {}, json.dumps({"id": "q1"}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/questoes/records",
                          callback=cap, content_type="application/json")
    payload = [{"tipo": "aberta", "enunciado": "Com imagem", "imagem": PNG_B64}]
    resp = client.post("/professor/disciplina/disc01/importar-questoes",
                       data={"acao": "importar", "json_text": json.dumps(payload)})
    assert resp.status_code == 200
    assert "multipart/form-data" in captured.get("ctype", "")
    assert captured.get("has_file")


@rsps_lib.activate
def test_previsualizar_mostra_resumo_sem_gravar(client):
    _sess_prof(client)
    _mock_disc()
    # Nenhum POST a questoes/records deve ocorrer no dry-run; se ocorrer, responses
    # levanta erro por URL não registrada — garantindo que nada foi gravado.
    payload = [
        {"tipo": "mc4", "enunciado": "Q1", "alternativas": [{"letra": "A", "texto": "x", "correta": True}]},
        {"tipo": "vf", "enunciado": "Q2", "itens_vf": [{"afirmacao": "a", "correta": True}]},
        {"tipo": "mc4", "enunciado": "ruim", "alternativas": [{"letra": "A", "texto": "x", "correta": False}]},
    ]
    resp = client.post("/professor/disciplina/disc01/importar-questoes",
                       data={"acao": "previsualizar", "json_text": json.dumps(payload)})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "2" in html and "serão criadas" in html      # 2 válidas
    assert "com problema" in html                         # 1 inválida
    assert "Confirmar importação" in html                 # botão de confirmação
    assert "sem alternativa correta" in html              # motivo do problema


@rsps_lib.activate
def test_previsualizar_e_default_sem_acao(client):
    """Sem 'acao', o POST cai na pré-visualização (não importa)."""
    _sess_prof(client)
    _mock_disc()
    payload = [{"tipo": "aberta", "enunciado": "Disserte"}]
    resp = client.post("/professor/disciplina/disc01/importar-questoes",
                       data={"json_text": json.dumps(payload)})
    assert resp.status_code == 200
    assert "Confirmar importação" in resp.data.decode()


@rsps_lib.activate
def test_importar_json_invalido_mostra_erro(client):
    _sess_prof(client)
    _mock_disc()
    resp = client.post("/professor/disciplina/disc01/importar-questoes",
                       data={"json_text": "{ nao eh json"})
    assert resp.status_code == 200
    assert "JSON inválido" in resp.data.decode()


@rsps_lib.activate
def test_importar_questao_invalida_reportada(client):
    _sess_prof(client)
    _mock_disc()
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/questoes/records", json={"id": "q1"})
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/itens_vf/records", json={"id": "i1"})
    # uma válida (vf) + duas inválidas (tipo ruim, mc sem correta)
    payload = [
        {"tipo": "vf", "enunciado": "ok", "itens_vf": [{"afirmacao": "a", "correta": True}]},
        {"tipo": "xyz", "enunciado": "tipo invalido"},
        {"tipo": "mc4", "enunciado": "sem gabarito", "alternativas": [{"letra": "A", "texto": "a", "correta": False}]},
    ]
    resp = client.post("/professor/disciplina/disc01/importar-questoes",
                       data={"acao": "importar", "json_text": json.dumps(payload)})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "1 de 3" in html
    assert "tipo inválido" in html
    assert "sem alternativa correta" in html


# ── Deduplicação contra o banco existente ───────────────────────────────────────

QUESTAO_EXISTENTE = {"id": "qOLD", "tipo": "mc4", "enunciado": "  Qual é   a capital do Brasil?  ",
                     "disciplina": "disc01", "peso": 1}


@rsps_lib.activate
def test_importar_pula_questao_duplicada_do_banco(client):
    _sess_prof(client)
    _mock_disc()
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records",
                 json={"items": [QUESTAO_EXISTENTE]})
    criadas_cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/questoes/records",
                          callback=lambda r: (criadas_cap.append(json.loads(r.body)), (200, {}, json.dumps({"id": "qNEW"})))[1],
                          content_type="application/json")
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/alternativas/records", json={"id": "a1"})
    payload = [
        # mesmo enunciado (variação de espaços/maiúsculas) e mesmo tipo → duplicata
        {"tipo": "mc4", "enunciado": "qual é a capital do brasil?",
         "alternativas": [{"letra": "A", "texto": "Brasília", "correta": True}]},
        # questão nova → deve ser criada normalmente
        {"tipo": "mc4", "enunciado": "Nova questão inédita",
         "alternativas": [{"letra": "A", "texto": "x", "correta": True}]},
    ]
    resp = client.post("/professor/disciplina/disc01/importar-questoes",
                       data={"acao": "importar", "json_text": json.dumps(payload)})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert len(criadas_cap) == 1, "só a questão nova deveria ter sido criada"
    assert criadas_cap[0]["enunciado"] == "Nova questão inédita"
    assert "1 de 2" in html
    assert "pulada" in html.lower()
    assert "idêntica a uma já existente no banco" in html.lower()


@rsps_lib.activate
def test_importar_detecta_duplicata_dentro_do_proprio_lote(client):
    """A mesma questão repetida duas vezes no JSON: só a primeira ocorrência é criada."""
    _sess_prof(client)
    _mock_disc()
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records", json={"items": []})
    criadas_cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/questoes/records",
                          callback=lambda r: (criadas_cap.append(json.loads(r.body)), (200, {}, json.dumps({"id": "qX"})))[1],
                          content_type="application/json")
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/alternativas/records", json={"id": "a1"})
    payload = [
        {"tipo": "mc4", "enunciado": "Repetida", "alternativas": [{"letra": "A", "texto": "x", "correta": True}]},
        {"tipo": "mc4", "enunciado": "Repetida", "alternativas": [{"letra": "A", "texto": "x", "correta": True}]},
    ]
    resp = client.post("/professor/disciplina/disc01/importar-questoes",
                       data={"acao": "importar", "json_text": json.dumps(payload)})
    assert resp.status_code == 200
    assert len(criadas_cap) == 1
    assert "1 de 2" in resp.data.decode()


@rsps_lib.activate
def test_previsualizar_marca_duplicata_do_banco(client):
    _sess_prof(client)
    _mock_disc()
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records",
                 json={"items": [QUESTAO_EXISTENTE]})
    payload = [{"tipo": "mc4", "enunciado": "qual é a capital do brasil?",
               "alternativas": [{"letra": "A", "texto": "Brasília", "correta": True}]}]
    resp = client.post("/professor/disciplina/disc01/importar-questoes",
                       data={"acao": "previsualizar", "json_text": json.dumps(payload)})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "já existem" in html.lower() or "já existe no banco" in html.lower()
    assert "0" in html  # nenhuma será criada


# ── Rollback: não deixar questão órfã quando o subitem falha ───────────────────

@rsps_lib.activate
def test_rollback_remove_questao_quando_alternativa_falha(client):
    _sess_prof(client)
    _mock_disc()
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records", json={"items": []})
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/questoes/records", json={"id": "qORFA"})
    # alternativa falha com 403 (simulando erro de permissão)
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/alternativas/records",
                 status=403, json={"code": 403, "message": "Only admins can create this record."})
    excluidas = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/qORFA",
                          callback=lambda r: (excluidas.append("qORFA"), (204, {}, ""))[1])
    payload = [{"tipo": "mc4", "enunciado": "Vai falhar",
               "alternativas": [{"letra": "A", "texto": "x", "correta": True}]}]
    resp = client.post("/professor/disciplina/disc01/importar-questoes",
                       data={"acao": "importar", "json_text": json.dumps(payload)})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "0 de 1" in html
    assert excluidas == ["qORFA"], "a questão órfã deveria ter sido removida (rollback)"
    assert "permissão negada" in html.lower() or "403" in html
    assert "questão removida" in html.lower()


@rsps_lib.activate
def test_rollback_apaga_alternativas_parciais_antes_de_excluir_a_questao(client):
    """Se a 2ª alternativa falhar, a 1ª já criada não pode impedir o rollback
    (o PocketBase recusaria apagar a questão com uma alternativa ainda presa a
    ela). O rollback precisa limpar os subitens parciais antes de excluir."""
    _sess_prof(client)
    _mock_disc()
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records", json={"items": []})
    rsps_lib.add(rsps_lib.POST, f"{PB}/api/collections/questoes/records", json={"id": "qORFA"})

    alt_posts = {"n": 0}

    def cap_alt_post(r):
        alt_posts["n"] += 1
        if alt_posts["n"] == 1:
            return (200, {}, json.dumps({"id": "altPARCIAL"}))
        return (403, {}, json.dumps({"message": "sem permissão"}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/alternativas/records",
                          callback=cap_alt_post, content_type="application/json")
    # apagar_subitens_questao busca a alternativa parcial e a remove
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": [{"id": "altPARCIAL"}]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/pares_associativos/records", json={"items": []})
    apagadas_alt = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/alternativas/records/altPARCIAL",
                          callback=lambda r: (apagadas_alt.append("altPARCIAL"), (204, {}, ""))[1])
    excluidas_questao = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/qORFA",
                          callback=lambda r: (excluidas_questao.append("qORFA"), (204, {}, ""))[1])

    payload = [{"tipo": "mc4", "enunciado": "Duas alternativas, a 2ª falha",
               "alternativas": [{"letra": "A", "texto": "ok", "correta": True},
                                 {"letra": "B", "texto": "vai falhar", "correta": False}]}]
    resp = client.post("/professor/disciplina/disc01/importar-questoes",
                       data={"acao": "importar", "json_text": json.dumps(payload)})
    assert resp.status_code == 200
    assert apagadas_alt == ["altPARCIAL"], "a alternativa parcial deveria ter sido limpa no rollback"
    assert excluidas_questao == ["qORFA"]
    assert "questão removida" in resp.data.decode().lower()


# ── Excluir em massa ─────────────────────────────────────────────────────────────

@rsps_lib.activate
def test_excluir_em_massa_remove_todas_as_selecionadas(client):
    _sess_prof(client)
    removidas_vinculo = []
    excluidas = []
    for qid in ("q1", "q2", "q3"):
        rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                     json={"items": []})
        rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/{qid}",
                              callback=(lambda qid: lambda r: (excluidas.append(qid), (204, {}, "")))(qid))
    resp = client.post("/professor/disciplina/disc01/questoes/excluir-em-massa",
                       data={"questoes": ["q1", "q2", "q3"]})
    assert resp.status_code in (200, 302)
    assert set(excluidas) == {"q1", "q2", "q3"}


@rsps_lib.activate
def test_excluir_em_massa_continua_apos_falha_individual(client):
    """Se uma exclusão falhar, as demais ainda devem ser processadas."""
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records", json={"items": []})
    rsps_lib.add(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/qBOA",
                 status=403, json={"message": "sem permissão"})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records", json={"items": []})
    excluidas = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/questoes/records/qOK",
                          callback=lambda r: (excluidas.append("qOK"), (204, {}, ""))[1])
    resp = client.post("/professor/disciplina/disc01/questoes/excluir-em-massa",
                       data={"questoes": ["qBOA", "qOK"]})
    assert resp.status_code in (200, 302)
    assert excluidas == ["qOK"], "a segunda exclusão deveria prosseguir mesmo após a primeira falhar"
