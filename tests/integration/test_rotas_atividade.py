"""Testes de integração para rotas de atividade (PocketBase mockado com responses)."""
import json
import responses as rsps_lib
import pytest


PB = "http://pb.test"

ATIVIDADE = {
    "id": "ativ01",
    "titulo": "Quiz Hematologia",
    "questoes": ["q001mc4"],
    "embaralhar": False,
}


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
