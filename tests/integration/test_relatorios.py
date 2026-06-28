"""Testes de integração para rotas de relatórios."""


def test_relatorio_turma_ok(client):
    resp = client.get("/relatorio/turma/turma01")
    assert resp.status_code == 200


def test_relatorio_aluno_ok(client):
    resp = client.get("/relatorio/aluno/aluno01")
    assert resp.status_code == 200
