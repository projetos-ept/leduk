"""Banco geral de questões (todas as disciplinas) + atividade multidisciplinar."""
import json

import responses as rsps_lib

PB = "http://pb.test"

DISCIPLINAS = [
    {"id": "disc01", "nome": "Informática Aplicada"},
    {"id": "disc02", "nome": "Hematologia"},
]
Q1 = {"id": "q1", "tipo": "mc4", "enunciado": "Função dos eritrócitos?", "peso": 1,
      "assunto": "Hemácias", "disciplina": "disc02"}
Q2 = {"id": "q2", "tipo": "vf", "enunciado": "Fases do LIS", "peso": 1,
      "assunto": "Fases", "disciplina": "disc01"}


def _sess_prof(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok-prof"
        sess["role"] = "professor"
        sess["aluno_nome"] = "Lucas"


# ── Banco geral ─────────────────────────────────────────────────────────────────

@rsps_lib.activate
def test_banco_geral_lista_todas_disciplinas(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records",
                 json={"items": [Q1, Q2]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
                 json={"items": DISCIPLINAS})
    resp = client.get("/professor/banco-questoes")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Função dos eritrócitos?" in html and "Fases do LIS" in html
    # nome da disciplina aparece em cada card
    assert "Hematologia" in html and "Informática Aplicada" in html


@rsps_lib.activate
def test_banco_geral_filtra_por_disciplina_tipo_assunto(client):
    _sess_prof(client)
    urls = []

    def cap(r):
        urls.append(r.url)
        return (200, {}, json.dumps({"items": [Q1]}))

    rsps_lib.add_callback(rsps_lib.GET, f"{PB}/api/collections/questoes/records",
                          callback=cap, content_type="application/json")
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
                 json={"items": DISCIPLINAS})
    resp = client.get("/professor/banco-questoes?disciplina=disc02&tipo=mc4&assunto=Hem%C3%A1cias")
    assert resp.status_code == 200
    joined = " ".join(urls)
    assert "disciplina" in joined and "tipo" in joined and "assunto" in joined


# ── Atividade multidisciplinar ──────────────────────────────────────────────────

@rsps_lib.activate
def test_multidisciplinar_form_lista_selecionadas(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q1", json=Q1)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q2", json=Q2)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": DISCIPLINAS})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records",
                 json={"items": [{"id": "turma01", "nome": "5TACN1", "modalidade": "PROEJA"}]})
    resp = client.get("/professor/atividade/multidisciplinar?questoes=q1&questoes=q2")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "2 questões selecionadas" in html
    assert "Função dos eritrócitos?" in html and "Fases do LIS" in html
    assert "Disciplina principal" in html


@rsps_lib.activate
def test_multidisciplinar_cria_atividade_com_questoes_de_varias_disciplinas(client):
    _sess_prof(client)
    cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/atividades/records",
                          callback=lambda r: (cap.append(json.loads(r.body)), (200, {}, json.dumps({"id": "atvM"})))[1],
                          content_type="application/json")
    resp = client.post("/professor/atividade/multidisciplinar", data={
        "titulo": "Avaliação integrada", "turma": "turma01", "disciplina": "disc02",
        "valor_total": "10", "max_tentativas": "0", "tempo_limite": "0",
        "questoes": ["q1", "q2"],
    })
    assert resp.status_code in (200, 302)
    assert cap, "atividade não foi criada"
    assert cap[0]["titulo"] == "Avaliação integrada"
    assert cap[0]["questoes"] == ["q1", "q2"]
    assert cap[0]["turma"] == "turma01"
    assert "/professor/turma/turma01" in resp.headers.get("Location", "")
    assert cap[0]["multidisciplinar"] is True


# ── Aba dedicada Multidisciplinar no portal ─────────────────────────────────────

TURMA = {"id": "turma01", "nome": "5TACN1", "modalidade": "PROEJA"}
ATIV_MULTI = {
    "id": "atvM", "titulo": "Avaliação integrada", "questoes": ["q1", "q2"],
    "ativa": True, "disciplina": "disc02", "multidisciplinar": True,
    "disponivel_de": None, "disponivel_ate": None, "tempo_limite": 0,
    "expand": {"disciplina": DISCIPLINAS[1]},
}


@rsps_lib.activate
def test_portal_multidisciplinar_lista_atividades(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok-aluno"
        sess["aluno_id"] = "al1"
        sess["aluno_nome"] = "Aluno"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": [ATIV_MULTI]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records", json={"items": []})
    resp = client.get("/turma/turma01/multidisciplinar")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Multidisciplinar" in html
    assert "Avaliação integrada" in html


@rsps_lib.activate
def test_portal_disciplina_exclui_multidisciplinar(client):
    """Atividade multidisciplinar não aparece na aba da disciplina."""
    with client.session_transaction() as sess:
        sess["token"] = "tok-aluno"
        sess["aluno_id"] = "al1"
        sess["aluno_nome"] = "Aluno"
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc02", json=DISCIPLINAS[1])
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turma_materiais/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/materiais/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"items": [ATIV_MULTI]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records", json={"items": []})
    resp = client.get("/turma/turma01/disc02")
    assert resp.status_code == 200
    html = resp.data.decode()
    # a multidisciplinar é filtrada da aba da disciplina → mensagem de vazio
    assert "Nenhuma atividade disponível para esta disciplina." in html
    # mas o link da aba dedicada aparece no menu
    assert "/turma/turma01/multidisciplinar" in html
