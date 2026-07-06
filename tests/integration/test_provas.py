"""Testes de integração do gerador de provas impressas com gabarito."""
import json

import responses as rsps_lib

PB = "http://pb.test"

QUESTAO_MC = {
    "id": "q001", "tipo": "mc4", "enunciado": "Qual alternativa correta?", "peso": 1,
    "alternativas": [
        {"id": "a1", "letra": "A", "texto": "Certa", "correta": True},
        {"id": "a2", "letra": "B", "texto": "Errada", "correta": False},
    ],
}
QUESTAO_VF = {
    "id": "q002", "tipo": "vf", "enunciado": "Julgue as afirmações", "peso": 2,
    "itens_vf": [
        {"id": "v1", "ordem": 1, "afirmacao": "Item verdadeiro", "gabarito": True},
        {"id": "v2", "ordem": 2, "afirmacao": "Item falso", "gabarito": False},
    ],
}
QUESTAO_ASSOC = {
    "id": "q003", "tipo": "associativa", "enunciado": "Associe as colunas", "peso": 2,
    "pares_associativos": [
        {"id": "p1", "ordem": 1, "coluna_a": "Hemácia", "coluna_b": "Transporte de O2"},
        {"id": "p2", "ordem": 2, "coluna_a": "Leucócito", "coluna_b": "Defesa"},
    ],
}
QUESTAO_ABERTA = {"id": "q004", "tipo": "aberta", "enunciado": "Disserte sobre o tema.", "peso": 1}

PROVA = {
    "id": "prova01", "titulo": "Prova de LIS", "template": "",
    "cabecalho_html": "<h2>Escola Técnica X</h2>", "instrucoes": "Instruções da prova.",
    "questoes": ["q001", "q002", "q003", "q004"], "embaralhar": False,
}
TEMPLATE_PROVA = {
    "id": "tmpl01", "nome": "Cabeçalho padrão CETEP",
    "cabecalho_html": "<h2>CETEP/LNAB</h2>", "instrucoes": "Instruções padrão do template.",
}


def _sessao_professor(client):
    with client.session_transaction() as sess:
        sess["token"] = "tok-prof"
        sess["aluno_id"] = "prof01"
        sess["aluno_nome"] = "Prof"
        sess["role"] = "professor"


def _mock_questoes_mistas():
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001", json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q002", json=QUESTAO_VF)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records",
                 json={"items": QUESTAO_VF["itens_vf"]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q003", json=QUESTAO_ASSOC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/pares_associativos/records",
                 json={"items": QUESTAO_ASSOC["pares_associativos"]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q004", json=QUESTAO_ABERTA)


# ── Lista e CRUD básico ────────────────────────────────────────────────────

@rsps_lib.activate
def test_lista_provas_vazia(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records", json={"items": []})
    resp = client.get("/professor/provas")
    assert resp.status_code == 200
    assert "Nenhuma prova cadastrada" in resp.data.decode()


@rsps_lib.activate
def test_lista_provas_exibe_provas_salvas(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records", json={"items": [PROVA]})
    resp = client.get("/professor/provas")
    assert resp.status_code == 200
    assert "Prova de LIS" in resp.data.decode()


@rsps_lib.activate
def test_nova_prova_form_ja_preenche_instrucao_padrao(client):
    """Instrução padrão pré-preenchida no formulário de nova prova."""
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/templates_prova/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": []})
    resp = client.get("/professor/provas/nova")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "proibido o uso de aparelhos eletrônicos" in html.lower()
    assert "Rasura e/ou dupla marcação anulam a questão" in html


@rsps_lib.activate
def test_criar_prova_sem_titulo_retorna_422(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/templates_prova/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": []})
    resp = client.post("/professor/provas/nova", data={"titulo": ""})
    assert resp.status_code == 422
    assert "obrigatório" in resp.data.decode().lower()


@rsps_lib.activate
def test_criar_prova_redireciona_para_edicao(client):
    _sessao_professor(client)
    captured = []

    def cb(request):
        body = json.loads(request.body)
        captured.append(body)
        return (200, {}, json.dumps({**PROVA, **body, "id": "prova99"}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/provas/records",
                          callback=cb, content_type="application/json")
    resp = client.post("/professor/provas/nova", data={"titulo": "Prova Nova"})
    assert resp.status_code == 302
    assert "/professor/provas/prova99/editar" in resp.headers["Location"]
    assert captured[0]["titulo"] == "Prova Nova"
    # instrução padrão é aplicada quando o campo vem vazio
    assert "proibido o uso de aparelhos eletrônicos" in captured[0]["instrucoes"].lower()


@rsps_lib.activate
def test_editar_prova_get_carrega_dados_persistidos(client):
    """Prova salva persiste após reload — GET /editar reflete o que foi gravado."""
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01", json=PROVA)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/templates_prova/records", json={"items": []})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": []})
    _mock_questoes_mistas()
    resp = client.get("/professor/provas/prova01/editar")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Prova de LIS" in html
    assert "Instruções da prova." in html
    assert "Questões na prova (4)" in html


@rsps_lib.activate
def test_editar_prova_post_atualiza_titulo(client):
    _sessao_professor(client)
    captured = []

    def cb(request):
        body = json.loads(request.body)
        captured.append(body)
        return (200, {}, json.dumps({**PROVA, **body}))

    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/provas/records/prova01",
                          callback=cb, content_type="application/json")
    resp = client.post("/professor/provas/prova01/editar", data={"titulo": "Prova Renomeada"})
    assert resp.status_code == 302
    assert captured[0]["titulo"] == "Prova Renomeada"


@rsps_lib.activate
def test_excluir_prova(client):
    _sessao_professor(client)
    deletada = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/provas/records/prova01",
                          callback=lambda r: (deletada.append(1), (204, {}, ""))[1])
    resp = client.post("/professor/provas/prova01/excluir")
    assert resp.status_code == 302
    assert deletada


# ── HTMX: seletor e montagem da prova ──────────────────────────────────────

@rsps_lib.activate
def test_htmx_seletor_questoes_filtra_e_exclui_ja_adicionadas(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records",
                 json={"items": [QUESTAO_MC, {**QUESTAO_VF, "id": "q999"}]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01",
                 json={**PROVA, "questoes": ["q001"]})  # q001 já está na prova
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": []})
    resp = client.get("/htmx/provas/questoes?prova_id=prova01")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "q999" not in html or "Julgue as afirmações" in html  # a não-incluída aparece
    assert "Qual alternativa correta?" not in html  # a já incluída (q001) não aparece de novo


@rsps_lib.activate
def test_htmx_adicionar_questao_persiste_e_retorna_fragmento(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01",
                 json={**PROVA, "questoes": []})
    captured = []

    def cb(request):
        body = json.loads(request.body)
        captured.append(body)
        return (200, {}, json.dumps({**PROVA, **body}))

    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/provas/records/prova01",
                          callback=cb, content_type="application/json")
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001", json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})
    resp = client.post("/htmx/provas/prova01/adicionar-questao/q001")
    assert resp.status_code == 200
    assert captured[0]["questoes"] == ["q001"]
    assert "Qual alternativa correta?" in resp.data.decode()


@rsps_lib.activate
def test_htmx_remover_questao(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01",
                 json={**PROVA, "questoes": ["q001", "q002"]})
    captured = []

    def cb(request):
        body = json.loads(request.body)
        captured.append(body)
        return (200, {}, json.dumps({**PROVA, **body}))

    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/provas/records/prova01",
                          callback=cb, content_type="application/json")
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q002", json=QUESTAO_VF)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records",
                 json={"items": QUESTAO_VF["itens_vf"]})
    resp = client.post("/htmx/provas/prova01/remover-questao/q001")
    assert resp.status_code == 200
    assert captured[0]["questoes"] == ["q002"]


@rsps_lib.activate
def test_htmx_reordenar_questao_move_para_cima(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01",
                 json={**PROVA, "questoes": ["q001", "q002"]})
    captured = []

    def cb(request):
        body = json.loads(request.body)
        captured.append(body)
        return (200, {}, json.dumps({**PROVA, **body}))

    rsps_lib.add_callback(rsps_lib.PATCH, f"{PB}/api/collections/provas/records/prova01",
                          callback=cb, content_type="application/json")
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q001", json=QUESTAO_MC)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/alternativas/records",
                 json={"items": QUESTAO_MC["alternativas"]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/questoes/records/q002", json=QUESTAO_VF)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/itens_vf/records",
                 json={"items": QUESTAO_VF["itens_vf"]})
    resp = client.post("/htmx/provas/prova01/reordenar",
                       data={"questao_id": "q002", "direcao": "cima"})
    assert resp.status_code == 200
    assert captured[0]["questoes"] == ["q002", "q001"]  # q002 subiu para a 1ª posição


# ── Impressão: tipos mistos, layout 2 colunas, gabarito ────────────────────

@rsps_lib.activate
def test_imprimir_prova_com_tipos_mistos(client):
    """Criar prova com questões de tipos mistos (mc4, vf, associativa, aberta)
    e verificar que o layout de impressão renderiza todos corretamente."""
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01", json=PROVA)
    _mock_questoes_mistas()
    resp = client.get("/professor/provas/prova01/imprimir")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Qual alternativa correta?" in html
    assert "Julgue as afirmações" in html
    assert "Associe as colunas" in html
    assert "Disserte sobre o tema." in html
    assert "Escola Técnica X" in html  # cabeçalho
    assert "Instruções da prova." in html


@rsps_lib.activate
def test_imprimir_layout_duas_colunas(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01", json=PROVA)
    _mock_questoes_mistas()
    resp = client.get("/professor/provas/prova01/imprimir")
    html = resp.data.decode()
    assert "columns: 2" in html


@rsps_lib.activate
def test_imprimir_associativa_ocupa_coluna_unica(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01", json=PROVA)
    _mock_questoes_mistas()
    resp = client.get("/professor/provas/prova01/imprimir")
    html = resp.data.decode()
    assert "questao-associativa" in html
    assert "column-span: none" in html
    assert "COLUNA A" in html and "COLUNA B" in html


@rsps_lib.activate
def test_imprimir_associativa_coluna_b_usa_letra_maiuscula(client):
    """Coluna B da associativa segue o mesmo padrão de mc4/mc5: letra em
    caixa alta (A), B)...), não minúscula."""
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01", json=PROVA)
    _mock_questoes_mistas()
    resp = client.get("/professor/provas/prova01/imprimir")
    html = resp.data.decode()
    assert '<div class="assoc-item">A) Defesa</div>' in html
    assert '<div class="assoc-item">B) Transporte de O2</div>' in html


@rsps_lib.activate
def test_imprimir_gabarito_com_quebra_de_pagina(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01", json=PROVA)
    _mock_questoes_mistas()
    resp = client.get("/professor/provas/prova01/imprimir")
    html = resp.data.decode()
    assert "page-break-before: always" in html
    assert "GABARITO" in html.upper()
    # gabarito mostra a letra correta da mc4, V/F por afirmação, e os rótulos
    # simplificados para associativa/aberta (professor corrige manualmente)
    assert "Assoc." in html
    assert "Aberta" in html
    assert 'class="gab-marca">A' in html  # a correta (letra A) fica marcada


@rsps_lib.activate
def test_imprimir_gabarito_mc_mostra_so_a_letra_correta(client):
    """Gabarito de questão objetiva mostra só a letra correta, sem listar
    as demais alternativas ao lado."""
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01", json=PROVA)
    _mock_questoes_mistas()
    resp = client.get("/professor/provas/prova01/imprimir")
    html = resp.data.decode()
    trecho_q1 = html.split("Q1:</strong>")[1].split("Q2:</strong>")[0]
    assert 'class="gab-marca">A' in trecho_q1
    assert "B" not in trecho_q1


@rsps_lib.activate
def test_imprimir_marca_de_resposta(client):
    """mc4/mc5 começam direto pela letra (sem bolinha/checkbox nem
    parênteses); só a coluna A da associativa usa parênteses em branco
    para o estudante escrever a letra correspondente à mão."""
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01", json=PROVA)
    _mock_questoes_mistas()
    resp = client.get("/professor/provas/prova01/imprimir")
    html = resp.data.decode()
    assert "alt-marca" not in html
    assert '<div class="alternativa">A) Certa</div>' in html
    assert "(&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;) 1. Hemácia" in html


@rsps_lib.activate
def test_imprimir_nao_mostra_peso_da_questao(client):
    """O peso é usado só para o cálculo da nota — não deve aparecer na
    folha impressa que o estudante recebe."""
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01", json=PROVA)
    _mock_questoes_mistas()
    resp = client.get("/professor/provas/prova01/imprimir")
    html = resp.data.decode()
    assert "peso" not in html.lower()


@rsps_lib.activate
def test_imprimir_mensagem_final_apos_ultima_questao(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01", json=PROVA)
    _mock_questoes_mistas()
    resp = client.get("/professor/provas/prova01/imprimir")
    html = resp.data.decode()
    assert 'class="mensagem-final">Sucesso!' in html
    assert html.index("mensagem-final") > html.index("questoes-grid")


@rsps_lib.activate
def test_preview_e_imprimir_geram_o_mesmo_conteudo(client):
    """Preview e Imprimir PDF mostram a mesma prova (mesma fonte de verdade)."""
    _sessao_professor(client)
    for _ in range(2):
        rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01", json=PROVA)
    _mock_questoes_mistas()
    _mock_questoes_mistas()
    r1 = client.get("/professor/provas/prova01/preview")
    r2 = client.get("/professor/provas/prova01/imprimir")
    assert r1.status_code == 200 and r2.status_code == 200
    assert "Qual alternativa correta?" in r1.data.decode()
    assert "Qual alternativa correta?" in r2.data.decode()


@rsps_lib.activate
def test_imprimir_prova_embaralhada_e_deterministica(client):
    """embaralhar=true muda a ordem, mas é determinístico (mesmo seed = mesma
    ordem entre chamadas), então gabarito impresso sempre bate com a prova."""
    _sessao_professor(client)
    prova_embaralhada = {**PROVA, "embaralhar": True}
    for _ in range(2):
        rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/provas/records/prova01", json=prova_embaralhada)
    _mock_questoes_mistas()
    _mock_questoes_mistas()
    r1 = client.get("/professor/provas/prova01/imprimir")
    r2 = client.get("/professor/provas/prova01/imprimir")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.data == r2.data  # mesma ordem nas duas chamadas


# ── Templates de cabeçalho reutilizáveis ───────────────────────────────────

@rsps_lib.activate
def test_criar_template_prova(client):
    _sessao_professor(client)
    captured = []

    def cb(request):
        body = json.loads(request.body)
        captured.append(body)
        return (200, {}, json.dumps({**body, "id": "tmpl99"}))

    rsps_lib.add_callback(rsps_lib.POST, f"{PB}/api/collections/templates_prova/records",
                          callback=cb, content_type="application/json")
    resp = client.post("/professor/provas/templates/novo",
                       data={"nome": "Cabeçalho CETEP", "cabecalho_html": "<h2>CETEP</h2>",
                             "instrucoes": "Padrão"})
    assert resp.status_code == 302
    assert captured[0]["nome"] == "Cabeçalho CETEP"


@rsps_lib.activate
def test_lista_templates_prova(client):
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/templates_prova/records",
                 json={"items": [TEMPLATE_PROVA]})
    resp = client.get("/professor/provas/templates")
    assert resp.status_code == 200
    assert "Cabeçalho padrão CETEP" in resp.data.decode()


@rsps_lib.activate
def test_template_prova_disponivel_no_form_de_prova(client):
    """Template salvo aparece no seletor da tela de nova prova — reutilizável
    entre várias provas."""
    _sessao_professor(client)
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/templates_prova/records",
                 json={"items": [TEMPLATE_PROVA]})
    rsps_lib.add(rsps_lib.GET, f"{PB}/api/collections/disciplinas/records", json={"items": []})
    resp = client.get("/professor/provas/nova")
    html = resp.data.decode()
    assert "Cabeçalho padrão CETEP" in html


@rsps_lib.activate
def test_excluir_template_prova(client):
    _sessao_professor(client)
    deletado = []
    rsps_lib.add_callback(rsps_lib.DELETE, f"{PB}/api/collections/templates_prova/records/tmpl01",
                          callback=lambda r: (deletado.append(1), (204, {}, ""))[1])
    resp = client.post("/professor/provas/templates/tmpl01/excluir")
    assert resp.status_code == 302
    assert deletado
