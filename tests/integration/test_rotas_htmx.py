"""Testes de integração para rotas HTMX de interação (POST /htmx/responder)."""
import responses as rsps_lib
import pytest


PB = "http://pb.test"


@rsps_lib.activate
def test_responder_mc_correto(client, questao_mc4):
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

    resp = client.post(
        "/htmx/responder",
        data={"tipo": "mc4", "questao_id": "q001mc4", "resposta": "A"},
    )
    assert resp.status_code == 200


@rsps_lib.activate
def test_responder_mc_errado(client, questao_mc4):
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

    resp = client.post(
        "/htmx/responder",
        data={"tipo": "mc4", "questao_id": "q001mc4", "resposta": "B"},
    )
    assert resp.status_code == 200


@rsps_lib.activate
def test_responder_vf(client, questao_vf):
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

    resp = client.post(
        "/htmx/responder",
        data={
            "tipo": "vf",
            "questao_id": "q002vf",
            "vf_1": "true",
            "vf_2": "false",
            "vf_3": "true",
        },
    )
    assert resp.status_code == 200


@rsps_lib.activate
def test_responder_associativa(client, questao_associativa):
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/questoes/records/q003assoc",
        json=questao_associativa,
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{PB}/api/collections/pares_associativos/records",
        json={"items": questao_associativa["pares_associativos"]},
    )

    resp = client.post(
        "/htmx/responder",
        data={
            "tipo": "associativa",
            "questao_id": "q003assoc",
            "par_1": "Glicose",
            "par_2": "Ureia",
            "par_3": "Aspartato aminotransferase",
            "par_4": "Creatinina",
        },
    )
    assert resp.status_code == 200


def test_responder_tipo_invalido(client):
    resp = client.post(
        "/htmx/responder",
        data={"tipo": "desconhecido", "questao_id": "xxx"},
    )
    assert resp.status_code == 400


@rsps_lib.activate
def test_questao_mc_embaralha_alternativas(client, questao_mc4):
    """Alternativas são exibidas em ordem diferente da original (embaralhada)
    e o set de letras permanece completo."""
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
    with client.session_transaction() as sess:
        sess["tentativa_id"] = "tent-shuffle-test"
        sess["total"] = 1
        sess["fila"] = []
        sess["ativ_id"] = "ativ01"

    resp = client.get("/htmx/questao/q001mc4")
    assert resp.status_code == 200
    html = resp.data.decode()

    # todas as letras aparecem na resposta
    for letra in ("A", "B", "C", "D"):
        assert f'value="{letra}"' in html

    # a ordem de exibição deve diferir da original [A,B,C,D] com este seed
    import re
    letras_exibidas = re.findall(r'value="([A-E])"', html)
    assert sorted(letras_exibidas) == ["A", "B", "C", "D"]
    # com seed "tent-shuffle-testq001mc4" a ordem não é A,B,C,D
    assert letras_exibidas != ["A", "B", "C", "D"]
