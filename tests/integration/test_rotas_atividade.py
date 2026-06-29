"""Testes de integração para rotas de atividade (PocketBase mockado com responses)."""
import responses as rsps_lib


PB = "http://pb.test"

TURMA = {"id": "turma01", "nome": "1º Ano EMI", "modalidade": "EMI", "ano": "2025"}

DISCIPLINA = {"id": "disc01", "nome": "Hematologia"}

ATIVIDADE = {
    "id": "ativ01",
    "titulo": "Quiz Hematologia",
    "questoes": ["q001mc4"],
    "embaralhar": False,
    "ativa": True,
    "disponivel_de": None,
    "disponivel_ate": None,
    "tempo_limite": 0,
    "disciplina": "disc01",
    "expand": {"disciplina": DISCIPLINA},
}


@rsps_lib.activate
def test_home_lista_atividades_por_turma(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/turmas/records",
        json={"items": [TURMA]},
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/atividades/records",
        json={"items": [ATIVIDADE]},
    )

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Hematologia" in html              # nome da disciplina aparece
    assert '/turma/turma01/disc01' in html    # link para portal da disciplina
    assert '/atividade/ativ01' not in html    # home não linka direto para atividade
    assert '/atividade/turma01' not in html   # nunca linka por ID de turma


@rsps_lib.activate
def test_home_turma_sem_atividades_nao_exibe_secao(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/turmas/records",
        json={"items": [TURMA]},
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/atividades/records",
        json={"items": []},
    )

    resp = client.get("/")
    assert resp.status_code == 200
    assert "turma01" not in resp.data.decode()


@rsps_lib.activate
def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


@rsps_lib.activate
def test_atividade_inicia_sessao(client, questao_mc4):
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ01", json=ATIVIDADE)
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/questoes/records/q001mc4",
        json=questao_mc4,
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/alternativas/records",
        json={"items": questao_mc4["alternativas"]},
    )

    resp = client.get("/atividade/ativ01")
    assert resp.status_code == 200


@rsps_lib.activate
def test_htmx_questao_mc4(client, questao_mc4):
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/questoes/records/q001mc4",
        json=questao_mc4,
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/alternativas/records",
        json={"items": questao_mc4["alternativas"]},
    )

    resp = client.get("/htmx/questao/q001mc4")
    assert resp.status_code == 200


@rsps_lib.activate
def test_htmx_questao_vf(client, questao_vf):
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/questoes/records/q002vf",
        json=questao_vf,
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/itens_vf/records",
        json={"items": questao_vf["itens_vf"]},
    )

    resp = client.get("/htmx/questao/q002vf")
    assert resp.status_code == 200


@rsps_lib.activate
def test_atividade_sem_questoes(client):
    ativ_vazia = {**ATIVIDADE, "questoes": []}
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records/ativ99", json=ativ_vazia)

    resp = client.get("/atividade/ativ99")
    assert resp.status_code == 200
