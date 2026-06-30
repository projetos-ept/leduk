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
