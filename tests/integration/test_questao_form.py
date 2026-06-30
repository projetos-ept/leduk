"""Formulário de questão: seções condicionais por tipo + navegação cruzada banco.

As seções são mostradas/ocultadas por JS (atualizarCampos). Sem motor JS nos
testes, validamos o contrato estrutural que o JS usa: ids corretos, seções não
relevantes começam com display:none, e o tipo inicial passado à função reflete
o tipo salvo (modo edição) ou o padrão mc4 (nova questão).
"""
import responses as rsps_lib

PB = "http://pb.test"

ATIVIDADE = {"id": "ativ01", "titulo": "Prova", "questoes": [],
             "turma": "t1", "disciplina": "disc01"}
DISCIPLINA = {"id": "disc01", "nome": "Informática Aplicada"}
DISCIPLINAS = [DISCIPLINA, {"id": "disc02", "nome": "Hematologia"}]

Q_MC5 = {"id": "qMC5", "tipo": "mc5", "enunciado": "Questão MC5?", "disciplina": "disc01",
         "peso": 1, "dificuldade": "medio",
         "alternativas": [{"id": "a1", "letra": "A", "texto": "x", "correta": True}]}
Q_VF = {"id": "qVF", "tipo": "vf", "enunciado": "Questão VF?", "disciplina": "disc01",
        "peso": 1, "dificuldade": "medio",
        "itens_vf": [{"id": "i1", "afirmacao": "a", "correta": True, "ordem": 1}]}
Q_BANCO = {"id": "q1", "tipo": "mc4", "enunciado": "No banco?", "disciplina": "disc02",
           "assunto": "X", "peso": 1}


def _sess_prof(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok-prof"
        sess["role"] = "professor"
        sess["aluno_nome"] = "Lucas"


# ── Seções condicionais do formulário ───────────────────────────────────────────

@rsps_lib.activate
def test_form_nova_mc4_oculta_outras_secoes(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    resp = client.get("/professor/atividade/ativ01/questoes/nova")
    assert resp.status_code == 200
    html = resp.data.decode()
    # as 4 seções existem com os ids esperados
    for sid in ("secao-alternativas", "secao-vf", "secao-associativa", "secao-aberta"):
        assert f'id="{sid}"' in html
    # vf/associativa/aberta começam ocultas (display:none); alternativas não
    assert 'id="secao-vf" class="quest-secao" style="display:none;"' in html
    assert 'id="secao-associativa" class="quest-secao" style="display:none;"' in html
    assert 'id="secao-aberta" class="quest-secao" style="display:none;"' in html
    assert 'id="secao-alternativas" class="quest-secao" style="display:none;"' not in html
    # init com o tipo padrão mc4 + a 5ª alternativa controlada por classe
    assert 'const TIPO_ATUAL = "mc4"' in html
    assert "atualizarCampos(TIPO_ATUAL" in html
    assert "alt-mc5-only" in html


@rsps_lib.activate
def test_form_editar_mc5_inicia_no_tipo_salvo(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/qMC5", json=Q_MC5)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": Q_MC5["alternativas"]})
    resp = client.get("/professor/questao/qMC5/editar?ativ_id=ativ01")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'const TIPO_ATUAL = "mc5"' in html  # JS abre a seção de alternativas com A–E


@rsps_lib.activate
def test_form_editar_vf_inicia_no_tipo_salvo(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/qVF", json=Q_VF)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records",
                 json={"items": Q_VF["itens_vf"]})
    resp = client.get("/professor/questao/qVF/editar?ativ_id=ativ01")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'const TIPO_ATUAL = "vf"' in html  # JS abre VF e oculta alternativas/pares


# ── Navegação cruzada banco por disciplina ↔ seletor multidisciplinar ───────────

def _mock_banco_disc():
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=DISCIPLINA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": DISCIPLINAS})


@rsps_lib.activate
def test_banco_disciplina_tem_link_para_seletor(client):
    _sess_prof(client)
    _mock_banco_disc()
    resp = client.get("/professor/disciplina/disc01/banco-questoes")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Banco da Disciplina" in html
    assert "Selecionar para atividade multidisciplinar" in html
    assert "/professor/banco-questoes?disciplina=disc01" in html


@rsps_lib.activate
def test_seletor_multi_tem_edicao_por_questao_e_banner(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records", json={"items": [Q_BANCO]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": DISCIPLINAS})
    resp = client.get("/professor/banco-questoes?disciplina=disc02")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Seletor Multidisciplinar" in html
    # link de edição por questão → banco da disciplina da questão
    assert "Editar no banco" in html
    assert "/professor/disciplina/disc02/banco-questoes" in html
    # banner de disciplina filtrada
    assert "Mostrando questões de" in html
    assert "Hematologia" in html


@rsps_lib.activate
def test_drawer_tem_seletor_multidisciplinar(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": DISCIPLINAS})
    resp = client.get("/professor/banco-questoes")
    assert resp.status_code == 200
    assert "Seletor Multidisciplinar" in resp.data.decode()
