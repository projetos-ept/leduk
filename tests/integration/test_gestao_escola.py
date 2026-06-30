"""Gestão de turmas, disciplinas, vínculos e banco de materiais reutilizável."""
import json

import responses as rsps_lib

PB = "http://pb.test"

TURMA = {"id": "turma01", "nome": "5TACN1", "modalidade": "PROEJA", "ano": "2025", "ativa": True}
DISCIPLINA = {"id": "disc01", "nome": "Informática Aplicada", "codigo": "LIS"}
MATERIAL = {
    "id": "mat01", "titulo": "Introdução ao LIS", "tipo": "video",
    "url": "https://youtu.be/x", "descricao": "", "assunto": "Fases do LIS",
    "disciplina": "disc01", "ativo": True, "turma": "turma01",
}
MATERIAL2 = {
    "id": "mat02", "titulo": "Apostila LIS", "tipo": "pdf", "url": "https://x/p.pdf",
    "assunto": "Conformidade", "disciplina": "disc01", "ativo": True,
}


def _sess_prof(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok-prof"
        sess["role"] = "professor"
        sess["aluno_nome"] = "Lucas"


# ── Turmas ──────────────────────────────────────────────────────────────────────

@rsps_lib.activate
def test_criar_turma(client):
    _sess_prof(client)
    cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/turmas/records",
                          callback=lambda r: (cap.append(json.loads(r.body)), (200, {}, json.dumps({"id": "t9"})))[1],
                          content_type="application/json")
    resp = client.post("/professor/turma/nova",
                       data={"nome": "Nova Turma", "modalidade": "EMI", "ano": "2026", "ativa": "on"})
    assert resp.status_code in (200, 302)
    assert cap and cap[0]["nome"] == "Nova Turma"
    assert cap[0]["ativa"] is True


@rsps_lib.activate
def test_editar_turma(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    cap = []
    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/turmas/records/turma01",
                          callback=lambda r: (cap.append(json.loads(r.body)), (200, {}, json.dumps(TURMA)))[1],
                          content_type="application/json")
    resp = client.post("/professor/turma/turma01/editar",
                       data={"nome": "5TACN1 (renomeada)", "modalidade": "PROEJA", "ano": "2025"})
    assert resp.status_code in (200, 302)
    assert cap and "renomeada" in cap[0]["nome"]


@rsps_lib.activate
def test_excluir_turma_sem_vinculos(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turma_disciplina/records",
                 json={"totalItems": 0, "items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"totalItems": 0, "items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"totalItems": 0, "items": []})
    deleted = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/turmas/records/turma01",
                          callback=lambda r: (deleted.append(1), (204, {}, ""))[1])
    resp = client.post("/professor/turma/turma01/excluir")
    assert resp.status_code in (200, 302)
    assert deleted, "turma deveria ter sido excluída"


@rsps_lib.activate
def test_excluir_turma_com_vinculos_bloqueia(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turma_disciplina/records",
                 json={"totalItems": 2, "items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records",
                 json={"totalItems": 0, "items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/tentativas/records",
                 json={"totalItems": 0, "items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records",
                 json={"items": [TURMA]})
    resp = client.post("/professor/turma/turma01/excluir")
    assert resp.status_code == 422
    assert "Não foi possível excluir" in resp.data.decode()


# ── Disciplinas ───────────────────────────────────────────────────────────────

@rsps_lib.activate
def test_criar_disciplina(client):
    _sess_prof(client)
    cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/disciplinas/records",
                          callback=lambda r: (cap.append(json.loads(r.body)), (200, {}, json.dumps({"id": "d9"})))[1],
                          content_type="application/json")
    resp = client.post("/professor/disciplina/nova",
                       data={"nome": "Hematologia", "codigo": "HEM", "cor_tema": "#ff6b6b", "icone": "🩸", "ativa": "on"})
    assert resp.status_code in (200, 302)
    assert cap and cap[0]["nome"] == "Hematologia"
    assert cap[0]["codigo"] == "HEM"


@rsps_lib.activate
def test_excluir_disciplina_com_vinculos_bloqueia(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turma_disciplina/records",
                 json={"totalItems": 0, "items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records",
                 json={"totalItems": 5, "items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/materiais/records",
                 json={"totalItems": 0, "items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
                 json={"items": [DISCIPLINA]})
    resp = client.post("/professor/disciplina/disc01/excluir")
    assert resp.status_code == 422
    assert "Não foi possível excluir" in resp.data.decode()


# ── Vínculo turma ↔ disciplina ──────────────────────────────────────────────────

@rsps_lib.activate
def test_vincular_disciplina(client):
    _sess_prof(client)
    cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/turma_disciplina/records",
                          callback=lambda r: (cap.append(json.loads(r.body)), (200, {}, json.dumps({"id": "td1"})))[1],
                          content_type="application/json")
    resp = client.post("/professor/turma/turma01/disciplinas/vincular",
                       data={"disciplina": "disc01", "professor": "Ana", "semestre": "2025.1"})
    assert resp.status_code in (200, 302)
    assert cap and cap[0]["turma"] == "turma01" and cap[0]["disciplina"] == "disc01"
    assert cap[0]["professor"] == "Ana"


@rsps_lib.activate
def test_desvincular_disciplina(client):
    _sess_prof(client)
    deleted = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/turma_disciplina/records/td1",
                          callback=lambda r: (deleted.append(1), (204, {}, ""))[1])
    resp = client.post("/professor/turma/turma01/disciplinas/desvincular/td1")
    assert resp.status_code in (200, 302)
    assert deleted


# ── Banco de materiais ──────────────────────────────────────────────────────────

@rsps_lib.activate
def test_banco_materiais_lista_com_filtro(client):
    _sess_prof(client)
    urls = []

    def cap(r):
        urls.append(r.url)
        return (200, {}, json.dumps({"items": [MATERIAL]}))

    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=DISCIPLINA)
    rsps_lib.add_callback(rsps_lib.GET, f"{PB}/api/collections/materiais/records",
                          callback=cap, content_type="application/json")
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turma_materiais/records",
                 json={"totalItems": 0, "items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records",
                 json={"items": [DISCIPLINA]})
    resp = client.get("/professor/disciplina/disc01/banco-materiais?tipo=video")
    assert resp.status_code == 200
    assert "Introdução ao LIS" in resp.data.decode()
    assert any("tipo" in u for u in urls), "filtro de tipo não foi para a query"


@rsps_lib.activate
def test_clonar_material_duplica_registro(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/materiais/records/mat01", json=MATERIAL)
    cap = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/materiais/records",
                          callback=lambda r: (cap.append(json.loads(r.body)), (200, {}, json.dumps({"id": "matNEW"})))[1],
                          content_type="application/json")
    resp = client.post("/professor/material/mat01/clonar")
    assert resp.status_code in (200, 302)
    assert cap and "cópia" in cap[0]["titulo"]
    assert cap[0]["disciplina"] == "disc01"
    assert "turma" not in cap[0], "clone não deve carregar vínculo direto de turma"


@rsps_lib.activate
def test_reclassificar_material(client):
    _sess_prof(client)
    cap = []
    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/materiais/records/mat01",
                          callback=lambda r: (cap.append(json.loads(r.body)), (200, {}, json.dumps({"id": "mat01"})))[1],
                          content_type="application/json")
    resp = client.post("/professor/material/mat01/reclassificar",
                       data={"disciplina": "disc02", "assunto": "Novo", "origem_disciplina": "disc01"})
    assert resp.status_code in (200, 302)
    assert cap and cap[0]["disciplina"] == "disc02" and cap[0]["assunto"] == "Novo"


@rsps_lib.activate
def test_excluir_material_em_uso_faz_cascade(client):
    _sess_prof(client)
    # 2 vínculos em turma_materiais referenciam o material
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turma_materiais/records",
                 json={"items": [{"id": "tm1"}, {"id": "tm2"}]})
    del_pivo = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/turma_materiais/records/tm1",
                          callback=lambda r: (del_pivo.append("tm1"), (204, {}, ""))[1])
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/turma_materiais/records/tm2",
                          callback=lambda r: (del_pivo.append("tm2"), (204, {}, ""))[1])
    del_mat = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/materiais/records/mat01",
                          callback=lambda r: (del_mat.append(1), (204, {}, ""))[1])
    resp = client.post("/professor/material/mat01/excluir", data={"origem_disciplina": "disc01"})
    assert resp.status_code in (200, 302)
    assert set(del_pivo) == {"tm1", "tm2"}, "vínculos turma_materiais não foram limpos"
    assert del_mat, "material não foi excluído"


@rsps_lib.activate
def test_adicionar_material_a_turma_nao_duplica(client):
    _sess_prof(client)
    # matJA já vinculado (totalItems 1), matNOVO não (0)
    def cap_check(r):
        ja = "matJA" in r.url
        return (200, {}, json.dumps({"totalItems": 1 if ja else 0, "items": []}))

    rsps_lib.add_callback(rsps_lib.GET, f"{PB}/api/collections/turma_materiais/records",
                          callback=cap_check, content_type="application/json")
    posted = []
    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/turma_materiais/records",
                          callback=lambda r: (posted.append(json.loads(r.body)), (200, {}, json.dumps({"id": "tmX"})))[1],
                          content_type="application/json")
    resp = client.post("/professor/turma/turma01/materiais/adicionar",
                       data={"materiais": ["matJA", "matNOVO"]})
    assert resp.status_code in (200, 302)
    ids = [p["material"] for p in posted]
    assert ids == ["matNOVO"], "só o material novo deveria ser vinculado (sem duplicar)"


# ── Smoke: páginas renderizam sem erro de template ──────────────────────────────

@rsps_lib.activate
def test_turmas_lista_render(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records", json={"items": [TURMA]})
    assert client.get("/professor/turmas").status_code == 200


@rsps_lib.activate
def test_turma_form_nova_render(client):
    _sess_prof(client)
    r = client.get("/professor/turma/nova")
    assert r.status_code == 200 and "Nova turma" in r.data.decode()


@rsps_lib.activate
def test_disciplinas_lista_render(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": [DISCIPLINA]})
    assert client.get("/professor/disciplinas").status_code == 200


@rsps_lib.activate
def test_disciplina_form_nova_render(client):
    _sess_prof(client)
    r = client.get("/professor/disciplina/nova")
    assert r.status_code == 200 and "Nova disciplina" in r.data.decode()


@rsps_lib.activate
def test_material_form_novo_render(client):
    _sess_prof(client)
    r = client.get("/professor/material/novo?disciplina=disc01")
    assert r.status_code == 200 and "Novo material" in r.data.decode()


@rsps_lib.activate
def test_turma_disciplinas_render(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turma_disciplina/records",
                 json={"items": [{"id": "td1", "disciplina": "disc01", "professor": "Ana",
                                  "expand": {"disciplina": DISCIPLINA}}]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": [DISCIPLINA]})
    r = client.get("/professor/turma/turma01/disciplinas")
    assert r.status_code == 200 and "Informática Aplicada" in r.data.decode()


@rsps_lib.activate
def test_turma_materiais_render(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turma_materiais/records",
                 json={"items": [{"id": "tm1", "material": "mat01", "expand": {"material": MATERIAL}}]})
    r = client.get("/professor/turma/turma01/materiais")
    assert r.status_code == 200 and "Introdução ao LIS" in r.data.decode()


@rsps_lib.activate
def test_selecionar_materiais_render(client):
    _sess_prof(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turma_materiais/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/materiais/records", json={"items": [MATERIAL2]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": [DISCIPLINA]})
    r = client.get("/professor/turma/turma01/materiais/selecionar?disciplina=disc01")
    assert r.status_code == 200 and "Apostila LIS" in r.data.decode()


# ── Portal do aluno após migração de modelo ─────────────────────────────────────

@rsps_lib.activate
def test_portal_exibe_materiais_via_turma_materiais(client):
    """Sem login: portal lê materiais pelo pivô turma_materiais (modelo novo)."""
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turmas/records/turma01", json=TURMA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records/disc01", json=DISCIPLINA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/turma_materiais/records", json={"items": [
        {"id": "tm1", "material": "mat01", "ativo": True, "ordem": 1,
         "expand": {"material": MATERIAL}},
    ]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/atividades/records", json={"items": []})
    resp = client.get("/turma/turma01/disc01")
    assert resp.status_code == 200
    assert "Introdução ao LIS" in resp.data.decode()
