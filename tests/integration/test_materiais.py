"""Testes de upload de arquivo para materiais (PocketBase file storage)."""
import io
import json

import pytest
import responses as rsps_lib

from pb import PocketBaseClient

PB = "http://pb.test"

DISCIPLINA_ID = "disc01"
MATERIAL_ID = "mat01"

MATERIAL_COM_ARQUIVO = {
    "id": MATERIAL_ID,
    "titulo": "Hemostasia PDF",
    "tipo": "pdf",
    "url": "",
    "arquivo": "hemostasia.pdf",
    "descricao": "",
    "disciplina": DISCIPLINA_ID,
    "assunto": "",
    "ativo": True,
}

MATERIAL_COM_URL = {
    "id": "mat02",
    "titulo": "Vídeo Hematologia",
    "tipo": "video",
    "url": "https://youtube.com/watch?v=abc123",
    "arquivo": "",
    "descricao": "",
    "disciplina": DISCIPLINA_ID,
    "assunto": "",
    "ativo": True,
}


def _sess_prof(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok-prof"
        sess["role"] = "professor"
        sess["aluno_nome"] = "Prof. Ana"


# ── url_arquivo_material ──────────────────────────────────────────────────────

def test_url_arquivo_material_retorna_url_pocketbase_quando_arquivo(monkeypatch):
    monkeypatch.setenv("PB_PUBLIC_URL", "https://pb.repoept.duckdns.org")
    pb = PocketBaseClient("http://pb.test")
    url = pb.url_arquivo_material(MATERIAL_COM_ARQUIVO)
    assert url == "https://pb.repoept.duckdns.org/api/files/izszkyi16wtznur/mat01/hemostasia.pdf"


def test_url_arquivo_material_retorna_url_externa_quando_sem_arquivo():
    pb = PocketBaseClient("http://pb.test")
    url = pb.url_arquivo_material(MATERIAL_COM_URL)
    assert url == "https://youtube.com/watch?v=abc123"


def test_url_arquivo_material_retorna_none_quando_sem_url_e_sem_arquivo():
    pb = PocketBaseClient("http://pb.test")
    url = pb.url_arquivo_material({"id": "x", "arquivo": "", "url": ""})
    assert url is None


# ── Criação de material via rota ──────────────────────────────────────────────

@rsps_lib.activate
def test_criar_material_com_arquivo_envia_multipart(client):
    """POST com arquivo → PocketBase recebe requisição multipart."""
    _sess_prof(client)

    captured_content_type = []

    def capture(req):
        captured_content_type.append(req.headers.get("Content-Type", ""))
        return (200, {}, json.dumps({"id": MATERIAL_ID, "titulo": "Hemostasia"}))

    rsps_lib.add_callback(
        rsps_lib.POST, f"{PB}/api/collections/materiais/records",
        callback=capture, content_type="application/json",
    )
    rsps_lib.add(
        rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
        json={"items": [{"id": DISCIPLINA_ID, "nome": "Hematologia"}]},
    )

    data = {
        "titulo": "Hemostasia",
        "tipo": "pdf",
        "url": "",
        "descricao": "",
        "assunto": "",
        "disciplina": DISCIPLINA_ID,
    }
    resp = client.post(
        "/professor/material/novo",
        data={**data, "arquivo": (io.BytesIO(b"%PDF-1.4 fake"), "hemostasia.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (200, 302)
    assert captured_content_type, "POST para PocketBase não foi feito"
    assert "multipart" in captured_content_type[0]


@rsps_lib.activate
def test_criar_material_sem_arquivo_envia_json(client):
    """POST sem arquivo (só URL) → PocketBase recebe requisição JSON."""
    _sess_prof(client)

    captured_content_type = []

    def capture(req):
        captured_content_type.append(req.headers.get("Content-Type", ""))
        return (200, {}, json.dumps({"id": "mat03", "titulo": "Vídeo"}))

    rsps_lib.add_callback(
        rsps_lib.POST, f"{PB}/api/collections/materiais/records",
        callback=capture, content_type="application/json",
    )
    rsps_lib.add(
        rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
        json={"items": [{"id": DISCIPLINA_ID, "nome": "Hematologia"}]},
    )

    resp = client.post(
        "/professor/material/novo",
        data={
            "titulo": "Vídeo",
            "tipo": "video",
            "url": "https://youtube.com/watch?v=abc",
            "descricao": "",
            "assunto": "",
            "disciplina": DISCIPLINA_ID,
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code in (200, 302)
    assert captured_content_type, "POST para PocketBase não foi feito"
    assert "application/json" in captured_content_type[0]
