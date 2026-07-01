import base64
import binascii
import json
import logging
import mimetypes
import os
import random
import re
import secrets
import string
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

import requests
from flask import Flask, make_response, redirect, render_template, request, session, url_for

from boletim import calcular_boletim_aluno, calcular_boletim_turma
from pb import PocketBaseClient
from utils.email import email_boas_vindas, email_redefinir_senha
from questao import (
    calcular_nota_final,
    calcular_valor_ponto,
    validar_associativa,
    validar_mc,
    validar_vf,
)

log = logging.getLogger(__name__)

_TEMPLATE_MAP = {
    "mc4": "components/_questao_mc.html",
    "mc5": "components/_questao_mc.html",
    "vf": "components/_questao_vf.html",
    "associativa": "components/_questao_assoc.html",
}


_CAMPOS_PB = {"id", "created", "updated", "collectionId", "collectionName", "expand"}


def _criar_subitems_questao(pb_inst, questao_id: str, tipo: str, form, files) -> None:
    """Cria alternativas / itens VF / pares associativos após criar uma questão."""
    if tipo in ("mc4", "mc5"):
        letras = list("ABCDE")[: 4 if tipo == "mc4" else 5]
        correta = form.get("correta", "A")
        for letra in letras:
            texto = form.get(f"alt_texto_{letra}", "").strip()
            if not texto:
                continue
            img = files.get(f"alt_imagem_{letra}")
            img_tuple = (img.filename, img.read(), img.content_type) if img and img.filename else None
            pb_inst.criar_alternativa(
                {
                    "questao": questao_id,
                    "letra": letra,
                    "texto": texto,
                    "correta": letra == correta,
                    "feedback": form.get(f"alt_feedback_{letra}", ""),
                },
                img_tuple,
            )
    elif tipo == "vf":
        for i in range(1, 21):
            af = form.get(f"vf_af_{i}", "").strip()
            if not af:
                break
            pb_inst.criar_item_vf({
                "questao": questao_id,
                "afirmacao": af,
                "gabarito": form.get(f"vf_ok_{i}") == "V",
                "ordem": i,
            })
    elif tipo == "associativa":
        for i in range(1, 21):
            col_a = form.get(f"par_a_{i}", "").strip()
            col_b = form.get(f"par_b_{i}", "").strip()
            if not col_a:
                break
            pb_inst.criar_par_associativo({
                "questao": questao_id,
                "coluna_a": col_a,
                "coluna_b": col_b,
                "ordem": i,
            })


def _questao_campos_comuns(form) -> dict:
    """Campos editáveis comuns a criação e edição de questão (sem tipo/disciplina)."""
    return {
        "enunciado": form.get("enunciado", ""),
        "peso": float(form.get("peso") or 1),
        "dificuldade": form.get("dificuldade", "medio"),
        "feedback_geral": form.get("feedback_geral", ""),
        "assunto": form.get("assunto", ""),
    }


def _form_to_turma(form) -> dict:
    return {
        "nome": form.get("nome", "").strip(),
        "modalidade": form.get("modalidade", ""),
        "ano": form.get("ano", "").strip(),
        "ativa": "ativa" in form,
    }


def _form_to_disciplina(form) -> dict:
    return {
        "nome": form.get("nome", "").strip(),
        "codigo": form.get("codigo", "").strip(),
        "cor_tema": form.get("cor_tema", "").strip(),
        "icone": form.get("icone", "").strip(),
        "ativa": "ativa" in form,
    }


def _material_campos_comuns(form) -> dict:
    """Campos editáveis comuns a criação e edição de material (sem tipo/disciplina)."""
    return {
        "titulo": form.get("titulo", "").strip(),
        "descricao": form.get("descricao", "").strip(),
        "url": form.get("url", "").strip(),
        "assunto": form.get("assunto", "").strip(),
    }


def _portal_url() -> str:
    return os.environ.get("PORTAL_URL", "https://leduk.repoept.duckdns.org").rstrip("/")


def _senha_temporaria(n: int = 8) -> str:
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(n))


def _pb_datetime(dt: datetime) -> str:
    """Formata um datetime para o formato de data do PocketBase."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.000Z")


def _form_to_boletim(form, turma_id: str) -> dict:
    ma = (form.get("media_aprovacao") or "").strip()
    ano = (form.get("ano") or "").strip()
    return {
        "turma": turma_id,
        "media_aprovacao": float(ma) if ma else 5.0,
        "ativo": "ativo" in form,
        "liberado": "liberado" in form,
        "ano": int(ano) if ano.isdigit() else None,
    }


def _form_to_unidade(form, boletim_id: str) -> dict:
    rec_manual = (form.get("rec_nota_manual") or "").strip()
    return {
        "boletim": boletim_id,
        "disciplina": form.get("disciplina", ""),
        "numero": int(form.get("numero") or 1),
        "titulo": form.get("titulo", "").strip(),
        "atividades": form.getlist("atividades"),
        "rec_atividade": form.get("rec_atividade", ""),
        "rec_nota_manual": float(rec_manual) if rec_manual else None,
    }


def _imagem_spec_to_tuple(spec):
    """Converte um campo de imagem do JSON de importação em (nome, bytes, content_type).

    Aceita data URI base64 (data:image/png;base64,...) e URL http(s). Qualquer
    falha (formato inválido, download que não responde) retorna None — a questão
    é importada sem imagem em vez de quebrar a importação inteira.
    """
    if not spec or not isinstance(spec, str):
        return None
    spec = spec.strip()
    if spec.startswith("data:"):
        try:
            header, b64 = spec.split(",", 1)
            ctype = (header[5:].split(";")[0] or "image/png").strip()
            data = base64.b64decode(b64)
            ext = mimetypes.guess_extension(ctype) or ".png"
            return (f"import{ext}", data, ctype)
        except (ValueError, binascii.Error):
            return None
    if spec.startswith(("http://", "https://")):
        try:
            r = requests.get(spec, timeout=15)
            r.raise_for_status()
            ctype = r.headers.get("Content-Type", "image/png").split(";")[0].strip()
            ext = mimetypes.guess_extension(ctype) or os.path.splitext(spec.split("?")[0])[1] or ".png"
            nome = os.path.basename(spec.split("?")[0]) or f"import{ext}"
            return (nome, r.content, ctype)
        except Exception:
            return None
    return None


def _chave_duplicata(tipo: str, enunciado: str) -> tuple:
    """Chave de comparação para detectar questões idênticas: tipo + enunciado
    normalizado (espaços colapsados, minúsculo)."""
    return (tipo, " ".join(enunciado.strip().lower().split()))


def _chaves_do_banco(existentes: list) -> set:
    return {_chave_duplicata(q.get("tipo", ""), q.get("enunciado", "")) for q in existentes}


_LETRAS_ALTERNATIVA = ["A", "B", "C", "D", "E"]


def _normalizar_alternativas(alternativas: list) -> list:
    """Garante que toda alternativa tenha o campo `letra`.

    Geradores externos de JSON (ex: NotebookLM) frequentemente omitem `letra`,
    enviando só `texto`/`correta`/`feedback`. O schema do PocketBase exige
    `letra`, então preenchemos automaticamente pela posição na lista
    (A, B, C, D, E) quando ausente — sem sobrescrever uma letra já informada.
    """
    resultado = []
    for i, alt in enumerate(alternativas):
        if not isinstance(alt, dict):
            resultado.append(alt)
            continue
        alt = dict(alt)
        if not alt.get("letra") and i < len(_LETRAS_ALTERNATIVA):
            alt["letra"] = _LETRAS_ALTERNATIVA[i]
        resultado.append(alt)
    return resultado


def _normalizar_itens_vf(itens: list) -> list:
    """Normaliza itens V/F vindos de geradores externos de JSON.

    Aceita `texto` como alias de `afirmacao` e `correta` como alias de
    `gabarito` (o campo real no PocketBase é `gabarito` — sempre normalizamos
    para ele; `correta` é aceito como alias de entrada).
    Preenche `ordem` pela posição quando ausente, sem sobrescrever um valor
    já informado.
    """
    resultado = []
    for i, item in enumerate(itens, 1):
        if not isinstance(item, dict):
            resultado.append(item)
            continue
        item = dict(item)
        if not item.get("afirmacao") and item.get("texto"):
            item["afirmacao"] = item.pop("texto")
        if "gabarito" not in item and "correta" in item:
            item["gabarito"] = item.pop("correta")
        if not item.get("ordem"):
            item["ordem"] = i
        resultado.append(item)
    return resultado


def _erro_http(exc: Exception) -> str:
    """Extrai uma mensagem legível de uma falha de chamada ao PocketBase,
    destacando especificamente erros de permissão (403) para que o professor
    saiba que é preciso revisar as regras de acesso da collection."""
    resp = getattr(exc, "response", None)
    if resp is not None:
        status = resp.status_code
        try:
            detalhe = resp.json().get("message", "") or resp.text[:200]
        except Exception:
            detalhe = resp.text[:200] if resp.text else ""
        if status == 403:
            return f"permissão negada (403) — verifique as regras de acesso (createRule) da collection. {detalhe}".strip()
        return f"HTTP {status}: {detalhe}".strip()
    return str(exc)


def _analisar_questoes(questoes: list, chaves_existentes: set | None = None) -> tuple[dict, list]:
    """Dry-run: valida a lista sem gravar nada. Retorna (resumo, itens) para a
    pré-visualização. Usa as mesmas regras de _importar_questoes, incluindo
    detecção de duplicatas contra o banco já existente e dentro do próprio lote."""
    tipos_validos = ("mc4", "mc5", "vf", "aberta", "associativa")
    chaves_vistas = set(chaves_existentes or set())
    itens = []
    por_tipo: dict[str, int] = {}
    validas = 0
    duplicadas = 0
    for i, q in enumerate(questoes, 1):
        item = {"num": i, "tipo": None, "enunciado": "", "assunto": "",
                "ok": True, "duplicada": False, "erro": "", "subitens": 0, "tem_imagem": False}
        if not isinstance(q, dict):
            item.update(ok=False, erro="formato inválido (esperado objeto)")
            itens.append(item)
            continue
        tipo = q.get("tipo")
        enunciado = (q.get("enunciado") or "").strip()
        item["tipo"] = tipo
        item["enunciado"] = enunciado
        item["assunto"] = q.get("assunto") or ""
        item["tem_imagem"] = bool(q.get("imagem"))
        if tipo not in tipos_validos:
            item.update(ok=False, erro=f"tipo inválido ({tipo!r})")
        elif not enunciado:
            item.update(ok=False, erro="enunciado vazio")
        elif tipo in ("mc4", "mc5"):
            alts = _normalizar_alternativas(q.get("alternativas") or [])
            item["subitens"] = len(alts)
            if not any(isinstance(a, dict) and a.get("correta") for a in alts):
                item.update(ok=False, erro="múltipla escolha sem alternativa correta")
        elif tipo == "vf":
            item["subitens"] = len(_normalizar_itens_vf(q.get("itens_vf") or q.get("itens") or []))
        elif tipo == "associativa":
            item["subitens"] = len(q.get("pares") or q.get("pares_associativos") or [])
        if item["ok"]:
            chave = _chave_duplicata(tipo, enunciado)
            if chave in chaves_vistas:
                item.update(ok=False, duplicada=True,
                           erro="questão idêntica já existe no banco (pulada)")
            else:
                chaves_vistas.add(chave)
                validas += 1
                por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
        if item["duplicada"]:
            duplicadas += 1
        itens.append(item)
    invalidas = len(questoes) - validas - duplicadas
    resumo = {"total": len(questoes), "validas": validas, "duplicadas": duplicadas,
              "invalidas": invalidas, "por_tipo": por_tipo}
    return resumo, itens


def _importar_questoes(pb_inst, disciplina_id: str, questoes: list) -> tuple[int, list, list]:
    """Importa uma lista de questões no banco da disciplina. Best-effort: importa
    as válidas, pula duplicatas (mesma disciplina+tipo+enunciado) e coleta
    mensagens de erro das demais. Retorna (criadas, duplicadas, erros).

    Atomicidade: se a criação de um subitem (alternativa/item V-F/par) falhar
    depois que a questão-pai já foi gravada, a questão-pai é removida (rollback
    best-effort) em vez de ficar órfã no banco só com o enunciado.
    """
    try:
        chaves_vistas = _chaves_do_banco(pb_inst.listar_questoes_disciplina(disciplina_id))
    except Exception as exc:
        log.warning("listar_questoes_disciplina falhou ao checar duplicatas: %s", exc)
        chaves_vistas = set()

    criadas = 0
    duplicadas: list[str] = []
    erros: list[str] = []
    for i, q in enumerate(questoes, 1):
        try:
            if not isinstance(q, dict):
                erros.append(f"Questão {i}: formato inválido (esperado objeto)")
                continue
            tipo = q.get("tipo")
            enunciado = (q.get("enunciado") or "").strip()
            if tipo not in ("mc4", "mc5", "vf", "aberta", "associativa"):
                erros.append(f"Questão {i}: tipo inválido ({tipo!r})")
                continue
            if not enunciado:
                erros.append(f"Questão {i}: enunciado vazio")
                continue
            if tipo in ("mc4", "mc5"):
                alts = _normalizar_alternativas(q.get("alternativas") or [])
                if not any(a.get("correta") for a in alts if isinstance(a, dict)):
                    erros.append(f"Questão {i}: múltipla escolha sem alternativa correta")
                    continue

            chave = _chave_duplicata(tipo, enunciado)
            if chave in chaves_vistas:
                duplicadas.append(f"Questão {i}: idêntica a uma já existente no banco (pulada)")
                continue

            img = _imagem_spec_to_tuple(q.get("imagem"))
            criada = pb_inst.criar_questao({
                "enunciado": enunciado,
                "tipo": tipo,
                "disciplina": disciplina_id,
                "peso": float(q.get("peso") or 1),
                "dificuldade": q.get("dificuldade") or "medio",
                "feedback_geral": q.get("feedback_geral") or "",
                "assunto": q.get("assunto") or "",
            }, img)
            qid = criada["id"]
            try:
                if tipo in ("mc4", "mc5"):
                    for a in _normalizar_alternativas(q.get("alternativas") or []):
                        if not isinstance(a, dict):
                            continue
                        pb_inst.criar_alternativa({
                            "questao": qid,
                            "letra": a.get("letra", ""),
                            "texto": a.get("texto", ""),
                            "correta": bool(a.get("correta")),
                            "feedback": a.get("feedback", ""),
                        }, _imagem_spec_to_tuple(a.get("imagem")))
                elif tipo == "vf":
                    itens = _normalizar_itens_vf(q.get("itens_vf") or q.get("itens") or [])
                    for j, it in enumerate(itens, 1):
                        if not isinstance(it, dict):
                            continue
                        pb_inst.criar_item_vf({
                            "questao": qid,
                            "afirmacao": it.get("afirmacao", ""),
                            "gabarito": bool(it.get("gabarito")),
                            "ordem": it.get("ordem") or j,
                        })
                elif tipo == "associativa":
                    pares = q.get("pares") or q.get("pares_associativos") or []
                    for j, p in enumerate(pares, 1):
                        if not isinstance(p, dict):
                            continue
                        pb_inst.criar_par_associativo({
                            "questao": qid,
                            "coluna_a": p.get("coluna_a", ""),
                            "coluna_b": p.get("coluna_b", ""),
                            "ordem": j,
                        })
            except Exception as exc_sub:
                # Rollback best-effort: não deixar a questão órfã (só enunciado, sem
                # alternativas). Apaga primeiro os subitens que chegaram a ser criados
                # antes da falha — o PocketBase recusa apagar a questão enquanto ainda
                # houver subitem referenciando-a via relation obrigatória.
                removida = False
                try:
                    pb_inst.apagar_subitens_questao(qid)
                    pb_inst.excluir_questao(qid)
                    removida = True
                except Exception:
                    pass
                status = "questão removida" if removida else "questão NÃO pôde ser removida — revise manualmente"
                erros.append(f"Questão {i}: falha ao criar alternativas/itens, {status} "
                            f"({_erro_http(exc_sub)})")
                continue

            chaves_vistas.add(chave)
            criadas += 1
        except Exception as exc:
            erros.append(f"Questão {i}: erro ao importar ({_erro_http(exc)})")
    return criadas, duplicadas, erros


def _build_detalhamento(respostas: list, atividade: dict) -> tuple[float | None, list]:
    """Returns (nota_final, detalhamento) from session respostas and atividade record."""
    nota_final = calcular_nota_final(respostas, atividade)
    valor_total = atividade.get("valor_total") or None
    detalhamento = []
    if valor_total and respostas:
        pesos = [float(r.get("_peso", 1)) for r in respostas]
        vp = calcular_valor_ponto(atividade, pesos)
        for r in respostas:
            peso = float(r.get("_peso", 1))
            raw = r.get("score_raw", 0) or 0
            mx = r.get("score_max", 0) or 0
            pts = round((raw / mx) * peso * vp, 2) if mx > 0 else 0.0
            detalhamento.append({
                "num": r.get("_num", len(detalhamento) + 1),
                "peso": peso,
                "correta": r.get("correta", False),
                "pontos": pts,
            })
    return nota_final, detalhamento


def _render_questao(questao: dict, num: int, total: int, ativ_id: str):
    template = _TEMPLATE_MAP.get(questao.get("tipo", ""), "components/_questao_mc.html")
    if questao.get("tipo") in ("mc4", "mc5") and questao.get("alternativas"):
        seed = session.get("tentativa_id", "") + questao.get("id", "")
        rng = random.Random(seed)
        questao = dict(questao, alternativas=rng.sample(questao["alternativas"], len(questao["alternativas"])))
    return render_template(template, questao=questao, num=num, total=total, ativ_id=ativ_id)


def _atividade_disponivel(ativ: dict) -> tuple[bool, str]:
    if not ativ.get("ativa", False):
        return False, "inativa"
    agora = time.time()
    de = ativ.get("disponivel_de")
    ate = ativ.get("disponivel_ate")
    if de:
        try:
            dt = datetime.fromisoformat(de.replace("Z", "+00:00"))
            if agora < dt.timestamp():
                return False, "ainda_nao"
        except Exception:
            pass
    if ate:
        try:
            dt = datetime.fromisoformat(ate.replace("Z", "+00:00"))
            if agora > dt.timestamp():
                return False, "expirada"
        except Exception:
            pass
    return True, ""



def _to_pb_date(value: str | None) -> str | None:
    """Converte 'YYYY-MM-DDTHH:MM' (datetime-local) para o formato ISO do PocketBase."""
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M")
        return dt.strftime("%Y-%m-%d %H:%M:%S.000Z")
    except ValueError:
        return None


def _form_to_atividade(form) -> dict:
    vt = (form.get("valor_total") or "").strip()
    return {
        "titulo": form.get("titulo", ""),
        "descricao": form.get("descricao", ""),
        "turma": form.get("turma", ""),
        "disciplina": form.get("disciplina", ""),
        "valor_total": float(vt) if vt else None,
        "max_tentativas": int(form.get("max_tentativas") or 0),
        "tempo_limite": int(form.get("tempo_limite") or 0),
        "disponivel_de": _to_pb_date(form.get("disponivel_de")),
        "disponivel_ate": _to_pb_date(form.get("disponivel_ate")),
        "nota_automatica": "nota_automatica" in form,
        "exibir_feedback_pos": "exibir_feedback_pos" in form,
        "embaralhar": "embaralhar" in form,
        "modo_prova": "modo_prova" in form,
        "ativa": "ativa" in form,
    }


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

    pb_url = os.environ.get("PB_URL", "http://127.0.0.1:8090")
    if config:
        app.config.update(config)
        pb_url = config.get("PB_URL", pb_url)
        if "SECRET_KEY" in config:
            app.secret_key = config["SECRET_KEY"]

    pb = PocketBaseClient(pb_url)
    app.extensions["pb"] = pb

    def get_pb() -> PocketBaseClient:
        """Retorna um PocketBaseClient com o token JWT da sessão atual."""
        return PocketBaseClient(pb_url, token=session.get("token"))

    def _disciplinas_da_turma(turma_id: str) -> list:
        """Disciplinas distintas de uma turma, derivadas das atividades (expand)."""
        try:
            ativs = get_pb().listar_todas_atividades_turma(turma_id)
        except Exception:
            return []
        seen: dict[str, dict] = {}
        for a in ativs:
            d = (a.get("expand") or {}).get("disciplina")
            if d and d.get("id") and d["id"] not in seen:
                seen[d["id"]] = d
        return list(seen.values())

    def _professor_nav() -> list:
        """Estrutura de navegação do professor (turmas + disciplinas) para o drawer.

        Só é construída para professor/admin em páginas completas (não fragmentos
        HTMX). Resiliente: qualquer falha de rede resulta em nav vazio — o drawer
        simplesmente não lista turmas, sem quebrar a renderização da página.
        """
        if session.get("role") not in ("professor", "admin"):
            return []
        if request.headers.get("HX-Request"):
            return []
        try:
            turmas = get_pb().listar_turmas()
        except Exception:
            return []
        nav = []
        for t in turmas:
            disciplinas = []
            try:
                ativs = get_pb().listar_todas_atividades_turma(t["id"])
                seen: dict[str, dict] = {}
                for a in ativs:
                    d = (a.get("expand") or {}).get("disciplina")
                    if d and d.get("id") and d["id"] not in seen:
                        seen[d["id"]] = d
                disciplinas = list(seen.values())
            except Exception:
                disciplinas = []
            nav.append({"turma": t, "disciplinas": disciplinas})
        return nav

    @app.context_processor
    def _inject_globals():
        return {
            "pb_url": pb_url,
            "session_role": session.get("role", ""),
            "professor_nav": _professor_nav(),
        }

    @app.template_filter("youtube_id")
    def _youtube_id_filter(url: str) -> str:
        m = re.search(
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
            url or "",
        )
        return m.group(1) if m else ""

    def requer_login(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not app.config.get("LOGIN_REQUIRED", True):
                return f(*args, **kwargs)
            if not session.get("token"):
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated


    def requer_professor(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not app.config.get("LOGIN_REQUIRED", True):
                role = session.get("role")
                if role is not None and role not in ("professor", "admin"):
                    return redirect(url_for("index"))
                return f(*args, **kwargs)
            if not session.get("token"):
                return redirect(url_for("login"))
            if session.get("role") not in ("professor", "admin"):
                return redirect(url_for("index"))
            return f(*args, **kwargs)
        return decorated

    # ------------------------------------------------------------------
    # Auth

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render_template("auth/login.html", erro=None)
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "")
        try:
            dados = get_pb().login_aluno(email, senha)
            session["token"] = dados["token"]
            session["aluno_id"] = dados["record"]["id"]
            session["aluno_nome"] = dados["record"].get("name", email)
            session["role"] = dados["record"].get("role", "aluno")
            session["ultimo_acesso"] = datetime.now(timezone.utc).isoformat()
            if session["role"] in ("professor", "admin"):
                return redirect(url_for("professor_dashboard"))
            return redirect(url_for("index"))
        except Exception:
            return render_template("auth/login.html", erro="Email ou senha incorretos."), 401

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ------------------------------------------------------------------
    # Utilitário

    @app.route("/health")
    def health():
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # Home

    @app.route("/")
    @requer_login
    def index():
        turmas = get_pb().listar_turmas()
        ultimo_acesso = session.get("ultimo_acesso", "")
        estrutura: dict[str, list] = {}
        for t in turmas:
            atividades = get_pb().listar_atividades_por_turma(t["id"])
            discs: dict[str, dict] = {}
            for a in atividades:
                disc = (a.get("expand") or {}).get("disciplina")
                if not disc:
                    continue
                did = disc["id"]
                if did not in discs:
                    discs[did] = {"id": did, "nome": disc.get("nome", ""), "atividades_count": 0, "novas_count": 0}
                discs[did]["atividades_count"] += 1
            if ultimo_acesso:
                for disc in discs.values():
                    try:
                        disc["novas_count"] = get_pb().contar_novas_atividades(t["id"], disc["id"], ultimo_acesso)
                    except Exception:
                        disc["novas_count"] = 0
            estrutura[t["id"]] = list(discs.values())
        aluno_nome = session.get("aluno_nome", "")
        return render_template("index.html", turmas=turmas, estrutura=estrutura, aluno_nome=aluno_nome)

    # ------------------------------------------------------------------
    # Portal de turma/disciplina

    def _enriquecer_atividades(atividades: list, aluno_id: str) -> None:
        """Calcula status/prazo/tentativas de cada atividade (in-place) para o portal."""
        for ativ in atividades:
            disponivel, motivo = _atividade_disponivel(ativ)
            ativ["_status"] = "disponivel" if disponivel else motivo
            if motivo == "ainda_nao" and ativ.get("disponivel_de"):
                try:
                    dt = datetime.fromisoformat(ativ["disponivel_de"].replace("Z", "+00:00"))
                    ativ["_abre_em"] = dt.strftime("%d/%m")
                except Exception:
                    ativ["_abre_em"] = ""
            ate = ativ.get("disponivel_ate")
            if ate:
                try:
                    dt = datetime.fromisoformat(ate.replace("Z", "+00:00"))
                    ativ["_prazo"] = dt.strftime("%d/%m/%Y")
                except Exception:
                    ativ["_prazo"] = ""
            else:
                ativ["_prazo"] = ""

            max_tent = int(ativ.get("max_tentativas", 0) or 0)
            ativ["_max_tentativas"] = max_tent
            ativ["_exibir_feedback"] = bool(ativ.get("exibir_feedback_pos", True))
            ativ["_tentativas_usadas"] = 0
            ativ["_melhor_nota"] = 0
            ativ["_nota_liberada"] = False
            ativ["_melhor_tentativa_id"] = None
            ativ["_questoes_respondidas"] = 0
            if aluno_id and ativ["_status"] == "disponivel":
                try:
                    st = get_pb().status_atividade_aluno(ativ["id"], aluno_id, max_tent)
                    ativ["_tentativas_usadas"] = st["tentativas_usadas"]
                    ativ["_melhor_nota"] = st["melhor_nota"]
                    ativ["_nota_liberada"] = st["nota_liberada"]
                    ativ["_melhor_tentativa_id"] = st["melhor_tentativa_id"]
                    ativ["_nota_final"] = st.get("melhor_nota_final")
                    if not st["pode_tentar"]:
                        ativ["_status"] = "realizada"
                    elif st["tentativas_usadas"] > 0:
                        ativ["_status"] = "tentar_novamente"
                except Exception as exc:
                    log.warning("status_atividade_aluno falhou: %s", exc)
                if ativ["_status"] in ("disponivel", "tentar_novamente"):
                    try:
                        prog = get_pb().progresso_tentativa_atual(ativ["id"], aluno_id)
                        if prog:
                            ativ["_status"] = "em_andamento"
                            ativ["_questoes_respondidas"] = prog.get("questoes_respondidas", 0)
                    except Exception as exc:
                        log.warning("progresso_tentativa_atual falhou: %s", exc)

    @app.route("/turma/<turma_id>/<disciplina_id>")
    def portal_turma(turma_id: str, disciplina_id: str):
        turma = get_pb().buscar_turma(turma_id)
        disciplina = get_pb().buscar_disciplina(disciplina_id)
        materiais = get_pb().listar_materiais(turma_id, disciplina_id)

        # Pre-compute PocketBase file URL for uploaded files
        for m in materiais:
            if m.get("tipo") == "arquivo" and m.get("arquivo"):
                m["_arquivo_url"] = f"{pb_url}/api/files/materiais/{m['id']}/{m['arquivo']}"

        todas_disciplinas = get_pb().listar_disciplinas_da_turma(turma_id)
        tem_multidisciplinar = bool(get_pb().listar_atividades_multidisciplinares(turma_id))
        try:
            _bol = get_pb().buscar_boletim_turma(turma_id)
            boletim_ativo = bool(_bol and _bol.get("ativo"))
        except Exception:
            boletim_ativo = False  # collection 'boletins' ausente (pré-migração) ou rede

        logado = bool(session.get("token"))
        aluno_id = session.get("aluno_id", "")
        if logado:
            atividades = get_pb().listar_atividades_por_disciplina(turma_id, disciplina_id)
            # Atividades multidisciplinares vivem na aba dedicada, não na disciplina.
            atividades = [a for a in atividades if not a.get("multidisciplinar")]
            _enriquecer_atividades(atividades, aluno_id)
        else:
            atividades = []

        aluno_nome = session.get("aluno_nome", "")
        return render_template(
            "turma/portal.html",
            turma=turma,
            disciplina=disciplina,
            atividades=atividades,
            materiais=materiais,
            logado=logado,
            aluno_nome=aluno_nome,
            todas_disciplinas=todas_disciplinas,
            tem_multidisciplinar=tem_multidisciplinar,
            boletim_ativo=boletim_ativo,
        )

    @app.route("/turma/<turma_id>/multidisciplinar")
    def portal_multidisciplinar(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        todas_disciplinas = get_pb().listar_disciplinas_da_turma(turma_id)
        logado = bool(session.get("token"))
        aluno_id = session.get("aluno_id", "")
        atividades = get_pb().listar_atividades_multidisciplinares(turma_id) if logado else []
        _enriquecer_atividades(atividades, aluno_id)
        return render_template(
            "turma/portal.html",
            turma=turma,
            disciplina={"id": "multidisciplinar", "nome": "Multidisciplinar"},
            atividades=atividades,
            materiais=[],
            logado=logado,
            aluno_nome=session.get("aluno_nome", ""),
            todas_disciplinas=todas_disciplinas,
            tem_multidisciplinar=True,
            modo_multidisciplinar=True,
        )

    # ------------------------------------------------------------------
    # Motor de atividades

    @app.route("/atividade/<ativ_id>")
    @requer_login
    def atividade(ativ_id: str):
        ativ = get_pb().buscar_atividade(ativ_id)

        disponivel, motivo = _atividade_disponivel(ativ)
        if not disponivel:
            return render_template("auth/atividade_indisponivel.html", atividade=ativ, motivo=motivo)

        aluno_id = session.get("aluno_id", "")
        aluno_nome = session.get("aluno_nome", "")
        max_tentativas = int(ativ.get("max_tentativas", 0) or 0)

        if max_tentativas > 0 and aluno_id:
            status = get_pb().status_atividade_aluno(ativ_id, aluno_id, max_tentativas)
            if not status["pode_tentar"]:
                return render_template("auth/atividade_indisponivel.html", atividade=ativ, motivo="esgotada")

        tentativas_usadas = 0
        if aluno_id:
            tentativas_usadas = len(get_pb().listar_tentativas_aluno(ativ_id, aluno_id))

        try:
            tent = get_pb().criar_tentativa(ativ_id, aluno_id, aluno_nome, tentativas_usadas + 1)
            session["tentativa_id"] = tent["id"]
        except Exception as exc:
            log.warning("criar_tentativa falhou: %s", exc)
            session["tentativa_id"] = ""

        session["nota_automatica"] = bool(ativ.get("nota_automatica", False))
        session["modo_prova"] = bool(ativ.get("modo_prova", False))
        session["max_tentativas"] = max_tentativas
        session["tentativa_concluida"] = False

        questoes = ativ.get("questoes", [])
        session["fila"] = questoes[1:]
        session["ativ_id"] = ativ_id
        session["respostas"] = []
        session["total"] = len(questoes)

        tempo_limite = ativ.get("tempo_limite", 0) or 0
        if tempo_limite:
            session["deadline"] = time.time() + tempo_limite * 60
            tempo_restante_seg = int(tempo_limite * 60)
        else:
            session.pop("deadline", None)
            tempo_restante_seg = 0
        session.modified = True

        primeira = questoes[0] if questoes else None
        return render_template(
            "quiz/shell.html",
            atividade=ativ,
            primeira_questao=primeira,
            total=len(questoes),
            tempo_restante_seg=tempo_restante_seg,
            aluno_nome=aluno_nome,
        )

    @app.route("/htmx/questao/<questao_id>")
    @requer_login
    def htmx_questao(questao_id: str):
        questao = get_pb().buscar_questao(questao_id)
        total = session.get("total", 0)
        num = total - len(session.get("fila", []))
        return _render_questao(questao, num, total, session.get("ativ_id", ""))

    @app.route("/htmx/responder", methods=["POST"])
    @requer_login
    def htmx_responder():
        tipo = request.form.get("tipo", "")
        questao_id = request.form.get("questao_id", "")
        ativ_id = session.get("ativ_id", "")

        if tipo not in ("mc4", "mc5", "vf", "associativa", "aberta"):
            return "", 400

        questao = get_pb().buscar_questao(questao_id)

        if tipo in ("mc4", "mc5"):
            resposta_raw = request.form.get("resposta", "")
            resultado = validar_mc(questao, resposta_raw)
        elif tipo == "vf":
            respostas = {
                k.removeprefix("vf_"): v == "true"
                for k, v in request.form.items()
                if k.startswith("vf_")
            }
            resultado = validar_vf(questao, respostas)
            resposta_raw = str(respostas)
        elif tipo == "aberta":
            resposta_raw = request.form.get("resposta_aberta", "")
            resultado = {
                "correta": False,
                "score_raw": 0,
                "score_max": 0,
                "feedback": questao.get("feedback_geral"),
            }
        else:
            respostas = {
                k.removeprefix("par_"): v
                for k, v in request.form.items()
                if k.startswith("par_")
            }
            resultado = validar_associativa(questao, respostas)
            resposta_raw = str(respostas)

        resultado["_peso"] = float(questao.get("peso") or 1)
        respostas_sessao = session.get("respostas", [])
        resultado["_num"] = len(respostas_sessao) + 1
        respostas_sessao.append(resultado)
        session["respostas"] = respostas_sessao
        session.modified = True

        tentativa_id = session.get("tentativa_id", "")
        try:
            get_pb().registrar_tentativa({
                "atividade": ativ_id,
                "questao": questao_id,
                "tipo_questao": tipo,
                "resposta_dada": str(resposta_raw),
                "correta": resultado["correta"],
                "score_raw": resultado["score_raw"],
                "score_max": resultado["score_max"],
                "duracao_seg": 0,
                "aluno_id": session.get("aluno_id", ""),
                "aluno_nome": session.get("aluno_nome", ""),
                "tentativa_id": tentativa_id,
            })
        except Exception as exc:
            log.warning("registrar_tentativa falhou: %s", exc)

        if tentativa_id:
            try:
                get_pb().atualizar_progresso(tentativa_id, len(respostas_sessao))
            except Exception as exc:
                log.warning("atualizar_progresso falhou: %s", exc)

        return render_template(
            "components/_feedback.html", resultado=resultado, questao=questao, ativ_id=ativ_id,
            modo_prova=session.get("modo_prova", False),
        )

    @app.route("/htmx/proxima/<ativ_id>")
    @requer_login
    def htmx_proxima(ativ_id: str):
        fila: list = session.get("fila", [])
        total = session.get("total", 0)

        if not fila:
            respostas = session.get("respostas", [])
            score_raw = sum(r.get("score_raw", 0) for r in respostas)
            score_max = sum(r.get("score_max", 0) for r in respostas)
            nota_automatica = session.get("nota_automatica", False)
            tentativa_id = session.get("tentativa_id", "")
            if tentativa_id and not session.get("tentativa_concluida", False):
                try:
                    get_pb().concluir_tentativa(tentativa_id, score_raw, score_max, nota_automatica)
                    session["tentativa_concluida"] = True
                    session.modified = True
                except Exception as exc:
                    log.warning("concluir_tentativa falhou: %s", exc)
            max_tent = session.get("max_tentativas", 0)
            aluno_id = session.get("aluno_id", "")
            tentativas_restantes = 0
            if max_tent > 0 and aluno_id:
                usadas = len(get_pb().listar_tentativas_aluno(ativ_id, aluno_id))
                tentativas_restantes = max(0, max_tent - usadas)
            exibir_feedback = False
            nota_final = None
            valor_total = None
            detalhamento: list = []
            try:
                ativ_data = get_pb().buscar_atividade(ativ_id)
                exibir_feedback = bool(ativ_data.get("exibir_feedback_pos", True))
                valor_total = ativ_data.get("valor_total") or None
                nota_final, detalhamento = _build_detalhamento(respostas, ativ_data)
                if nota_final is not None and tentativa_id:
                    try:
                        get_pb().patch_tentativa_nota_final(tentativa_id, nota_final)
                    except Exception as exc:
                        log.warning("patch_tentativa_nota_final falhou: %s", exc)
            except Exception as exc:
                log.warning("buscar_atividade no placar falhou: %s", exc)
            modo_prova = session.get("modo_prova", False)
            return render_template(
                "components/_placar.html",
                score_raw=score_raw,
                score_max=score_max,
                ativ_id=ativ_id,
                nota_automatica=nota_automatica,
                tentativas_restantes=tentativas_restantes,
                exibir_feedback=exibir_feedback,
                tentativa_id=tentativa_id,
                nota_final=nota_final,
                valor_total=valor_total,
                detalhamento=detalhamento,
                modo_prova=modo_prova,
            )

        proxima_id = fila.pop(0)
        session["fila"] = fila
        session.modified = True

        num = total - len(fila)
        questao = get_pb().buscar_questao(proxima_id)
        return _render_questao(questao, num, total, ativ_id)

    @app.route("/htmx/resultado/<ativ_id>")
    @requer_login
    def htmx_resultado(ativ_id: str):
        respostas = session.get("respostas", [])
        score_raw = sum(r.get("score_raw", 0) for r in respostas)
        score_max = sum(r.get("score_max", 0) for r in respostas)
        nota_automatica = session.get("nota_automatica", False)
        tentativa_id = session.get("tentativa_id", "")
        if tentativa_id and not session.get("tentativa_concluida", False):
            try:
                get_pb().concluir_tentativa(tentativa_id, score_raw, score_max, nota_automatica)
                session["tentativa_concluida"] = True
                session.modified = True
            except Exception as exc:
                log.warning("concluir_tentativa falhou: %s", exc)
        max_tent = session.get("max_tentativas", 0)
        aluno_id = session.get("aluno_id", "")
        tentativas_restantes = 0
        if max_tent > 0 and aluno_id:
            usadas = len(get_pb().listar_tentativas_aluno(ativ_id, aluno_id))
            tentativas_restantes = max(0, max_tent - usadas)
        exibir_feedback = False
        nota_final = None
        valor_total = None
        detalhamento: list = []
        try:
            ativ_data = get_pb().buscar_atividade(ativ_id)
            exibir_feedback = bool(ativ_data.get("exibir_feedback_pos", True))
            valor_total = ativ_data.get("valor_total") or None
            nota_final, detalhamento = _build_detalhamento(respostas, ativ_data)
            if nota_final is not None and tentativa_id:
                try:
                    get_pb().patch_tentativa_nota_final(tentativa_id, nota_final)
                except Exception as exc:
                    log.warning("patch_tentativa_nota_final falhou: %s", exc)
        except Exception as exc:
            log.warning("buscar_atividade no resultado falhou: %s", exc)
        modo_prova = session.get("modo_prova", False)
        return render_template(
            "components/_placar.html",
            score_raw=score_raw,
            score_max=score_max,
            ativ_id=ativ_id,
            nota_automatica=nota_automatica,
            tentativas_restantes=tentativas_restantes,
            exibir_feedback=exibir_feedback,
            tentativa_id=tentativa_id,
            nota_final=nota_final,
            valor_total=valor_total,
            detalhamento=detalhamento,
            modo_prova=modo_prova,
        )

    # ── Professor portal ──

    @app.route("/professor/dashboard")
    @requer_professor
    def professor_dashboard():
        turmas = get_pb().listar_turmas()
        turmas_data = []
        for turma in turmas:
            atividades = get_pb().listar_todas_atividades_turma(turma["id"])
            ativas_count = sum(1 for a in atividades if a.get("ativa"))
            pendentes = 0
            mapa: dict[str, dict] = {}
            for ativ in atividades:
                tentativas = get_pb().listar_tentativas_atividade(ativ["id"])
                pendentes += sum(1 for t in tentativas if not t.get("nota_liberada"))
                best: dict[str, dict] = {}
                for t in tentativas:
                    aid = t.get("aluno_id", "")
                    if not aid:
                        continue
                    if aid not in best or t.get("score_percentual", 0) > best[aid].get("score_percentual", 0):
                        best[aid] = t
                for aid, t in best.items():
                    if aid not in mapa:
                        mapa[aid] = {"nome": t.get("aluno_nome", aid), "notas": {}}
                    mapa[aid]["notas"][ativ["id"]] = t.get("score_percentual")
            alunos = sorted(mapa.values(), key=lambda a: a["nome"])
            disc_seen: dict[str, dict] = {}
            for a in atividades:
                d = (a.get("expand") or {}).get("disciplina")
                if d and d.get("id") and d["id"] not in disc_seen:
                    disc_seen[d["id"]] = d
            turmas_data.append({
                "turma": turma,
                "atividades": atividades,
                "ativas_count": ativas_count,
                "pendentes_count": pendentes,
                "alunos": alunos,
                "disciplinas": list(disc_seen.values()),
            })
        return render_template("professor/dashboard.html", turmas_data=turmas_data,
                               aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/turma/<turma_id>")
    @requer_professor
    def professor_turma(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        atividades = get_pb().listar_todas_atividades_turma(turma_id)
        disciplinas = get_pb().listar_disciplinas()
        disc_seen: dict[str, dict] = {}
        for ativ in atividades:
            disc = (ativ.get("expand") or {}).get("disciplina") or {}
            ativ["_disc_nome"] = disc.get("nome", "")
            if disc.get("id") and disc["id"] not in disc_seen:
                disc_seen[disc["id"]] = disc
        return render_template("professor/turma.html", turma=turma, atividades=atividades,
                               disciplinas=disciplinas, disciplinas_turma=list(disc_seen.values()),
                               aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/atividade/nova", methods=["GET", "POST"])
    @requer_professor
    def professor_atividade_nova():
        turmas = get_pb().listar_turmas()
        disciplinas = get_pb().listar_disciplinas()
        if request.method == "GET":
            return render_template("professor/atividade_form.html", atividade=None,
                                   turmas=turmas, disciplinas=disciplinas,
                                   turma_id=request.args.get("turma", ""),
                                   aluno_nome=session.get("aluno_nome", ""))
        data = _form_to_atividade(request.form)
        try:
            get_pb().criar_atividade(data)
        except Exception as exc:
            log.warning("criar_atividade falhou: %s", exc)
            return render_template("professor/atividade_form.html", atividade=None,
                                   turmas=turmas, disciplinas=disciplinas,
                                   turma_id=data.get("turma", ""),
                                   erro="Erro ao criar atividade.",
                                   aluno_nome=session.get("aluno_nome", "")), 422
        turma_id = data.get("turma", "")
        if request.headers.get("HX-Request"):
            r = make_response("", 204)
            r.headers["HX-Redirect"] = url_for("professor_turma", turma_id=turma_id)
            return r
        return redirect(url_for("professor_turma", turma_id=turma_id))

    @app.route("/professor/atividade/<ativ_id>/editar", methods=["GET", "POST"])
    @requer_professor
    def professor_atividade_editar(ativ_id: str):
        turmas = get_pb().listar_turmas()
        disciplinas = get_pb().listar_disciplinas()
        ativ = get_pb().buscar_atividade(ativ_id)
        if request.method == "GET":
            return render_template("professor/atividade_form.html", atividade=ativ,
                                   turmas=turmas, disciplinas=disciplinas,
                                   turma_id=ativ.get("turma", ""),
                                   aluno_nome=session.get("aluno_nome", ""))
        data = _form_to_atividade(request.form)
        try:
            get_pb().atualizar_atividade(ativ_id, data)
        except Exception as exc:
            log.warning("atualizar_atividade falhou: %s", exc)
            return render_template("professor/atividade_form.html", atividade=ativ,
                                   turmas=turmas, disciplinas=disciplinas,
                                   turma_id=data.get("turma", ativ.get("turma", "")),
                                   erro="Erro ao salvar atividade.",
                                   aluno_nome=session.get("aluno_nome", "")), 422
        turma_id = data.get("turma", ativ.get("turma", ""))
        if request.headers.get("HX-Request"):
            r = make_response("", 204)
            r.headers["HX-Redirect"] = url_for("professor_turma", turma_id=turma_id)
            return r
        return redirect(url_for("professor_turma", turma_id=turma_id))

    @app.route("/professor/atividade/<ativ_id>/toggle-ativa", methods=["POST"])
    @requer_professor
    def professor_toggle_ativa(ativ_id: str):
        ativ = get_pb().buscar_atividade(ativ_id)
        nova = not ativ.get("ativa", False)
        get_pb().atualizar_atividade(ativ_id, {"ativa": nova})
        return render_template("components/_toggle_ativa.html", ativ_id=ativ_id, ativa=nova)

    @app.route("/professor/atividade/<ativ_id>/notas")
    @requer_professor
    def professor_notas(ativ_id: str):
        ativ = get_pb().buscar_atividade(ativ_id)
        tentativas = get_pb().listar_tentativas_atividade(ativ_id)
        return render_template("professor/notas.html", atividade=ativ, tentativas=tentativas,
                               aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/atividade/<ativ_id>/liberar-notas", methods=["POST"])
    @requer_professor
    def professor_liberar_notas(ativ_id: str):
        ids = request.form.getlist("tentativa_ids")
        for tid in ids:
            try:
                get_pb().liberar_nota(tid)
            except Exception as exc:
                log.warning("liberar_nota falhou para %s: %s", tid, exc)
        return redirect(url_for("professor_notas", ativ_id=ativ_id))

    @app.route("/professor/notas-abertas/<ativ_id>")
    @requer_professor
    def professor_notas_abertas_alt(ativ_id: str):
        return redirect(url_for("professor_notas_abertas", ativ_id=ativ_id))

    @app.route("/professor/atividade/<ativ_id>/excluir", methods=["POST"])
    @requer_professor
    def professor_excluir_atividade(ativ_id: str):
        ativ = get_pb().buscar_atividade(ativ_id)
        turma_id = ativ.get("turma", "")
        get_pb().excluir_atividade(ativ_id)
        return redirect(url_for("professor_turma", turma_id=turma_id))

    @app.route("/professor/atividade/<ativ_id>/clonar", methods=["POST"])
    @requer_professor
    def professor_clonar_atividade(ativ_id: str):
        ativ = get_pb().buscar_atividade(ativ_id)
        turma_id = ativ.get("turma", "")
        data = {k: v for k, v in ativ.items() if k not in _CAMPOS_PB}
        data["titulo"] = f"{ativ['titulo']} (cópia)"
        data["ativa"] = False
        get_pb().criar_atividade(data)
        return redirect(url_for("professor_turma", turma_id=turma_id))

    @app.route("/professor/atividade/<ativ_id>/questoes")
    @requer_professor
    def professor_questoes_atividade(ativ_id: str):
        ativ = get_pb().buscar_atividade(ativ_id)
        questao_ids = ativ.get("questoes") or []
        questoes = get_pb().listar_questoes_atividade(questao_ids)
        return render_template("professor/questoes.html", ativ=ativ, questoes=questoes,
                               aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/atividade/<ativ_id>/questoes/nova", methods=["GET", "POST"])
    @requer_professor
    def professor_questao_nova(ativ_id: str):
        ativ = get_pb().buscar_atividade(ativ_id)
        if request.method == "GET":
            return render_template(
                "professor/questao_form.html", questao=None,
                form_action=url_for("professor_questao_nova", ativ_id=ativ_id),
                voltar_url=url_for("professor_questoes_atividade", ativ_id=ativ_id),
                ativ_id=ativ_id, disciplina_id=ativ.get("disciplina", ""),
                aluno_nome=session.get("aluno_nome", ""))
        tipo = request.form.get("tipo", "mc4")
        img = request.files.get("imagem")
        img_tuple = (img.filename, img.read(), img.content_type) if img and img.filename else None
        questao = get_pb().criar_questao({
            **_questao_campos_comuns(request.form),
            "tipo": tipo,
            "disciplina": ativ.get("disciplina", ""),
        }, img_tuple)
        _criar_subitems_questao(get_pb(), questao["id"], tipo, request.form, request.files)
        nova_lista = (ativ.get("questoes") or []) + [questao["id"]]
        get_pb().atualizar_atividade(ativ_id, {"questoes": nova_lista})
        return redirect(url_for("professor_questoes_atividade", ativ_id=ativ_id))

    @app.route("/professor/disciplina/<disciplina_id>/questao/nova", methods=["GET", "POST"])
    @requer_professor
    def professor_questao_nova_banco(disciplina_id: str):
        """Cria uma questão diretamente no banco da disciplina (sem vínculo a atividade)."""
        if request.method == "GET":
            return render_template(
                "professor/questao_form.html", questao=None,
                form_action=url_for("professor_questao_nova_banco", disciplina_id=disciplina_id),
                voltar_url=url_for("professor_banco_questoes", disciplina_id=disciplina_id),
                ativ_id="", disciplina_id=disciplina_id,
                aluno_nome=session.get("aluno_nome", ""))
        tipo = request.form.get("tipo", "mc4")
        img = request.files.get("imagem")
        img_tuple = (img.filename, img.read(), img.content_type) if img and img.filename else None
        questao = get_pb().criar_questao({
            **_questao_campos_comuns(request.form),
            "tipo": tipo,
            "disciplina": disciplina_id,
        }, img_tuple)
        _criar_subitems_questao(get_pb(), questao["id"], tipo, request.form, request.files)
        return redirect(url_for("professor_banco_questoes", disciplina_id=disciplina_id))

    @app.route("/professor/disciplina/<disciplina_id>/importar-questoes", methods=["GET", "POST"])
    @requer_professor
    def professor_importar_questoes(disciplina_id: str):
        disciplina = get_pb().buscar_disciplina(disciplina_id)
        if request.method == "GET":
            return render_template("professor/importar_questoes.html", disciplina=disciplina,
                                   aluno_nome=session.get("aluno_nome", ""))
        # Lê do arquivo .json se enviado; senão do texto colado.
        arquivo = request.files.get("json_file")
        if arquivo and arquivo.filename:
            raw = arquivo.read().decode("utf-8", errors="replace")
        else:
            raw = request.form.get("json_text", "")
        if not raw.strip():
            return render_template("professor/importar_questoes.html", disciplina=disciplina,
                                   erro="Cole o JSON ou envie um arquivo .json.",
                                   aluno_nome=session.get("aluno_nome", ""))
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            return render_template("professor/importar_questoes.html", disciplina=disciplina,
                                   erro=f"JSON inválido: {exc}", json_text=raw,
                                   aluno_nome=session.get("aluno_nome", ""))
        questoes = parsed.get("questoes") if isinstance(parsed, dict) else parsed
        if not isinstance(questoes, list):
            return render_template("professor/importar_questoes.html", disciplina=disciplina,
                                   erro='Esperado uma lista de questões ou um objeto {"questoes": [...]}.',
                                   json_text=raw, aluno_nome=session.get("aluno_nome", ""))
        acao = request.form.get("acao", "previsualizar")
        if acao == "importar":
            criadas, duplicadas, erros = _importar_questoes(get_pb(), disciplina_id, questoes)
            return render_template("professor/importar_questoes.html", disciplina=disciplina,
                                   criadas=criadas, duplicadas=duplicadas, erros=erros,
                                   total=len(questoes), aluno_nome=session.get("aluno_nome", ""))
        # Pré-visualização (dry-run, sem gravar)
        try:
            chaves_existentes = _chaves_do_banco(get_pb().listar_questoes_disciplina(disciplina_id))
        except Exception as exc:
            log.warning("listar_questoes_disciplina falhou na pré-visualização: %s", exc)
            chaves_existentes = set()
        resumo, itens = _analisar_questoes(questoes, chaves_existentes)
        return render_template("professor/importar_questoes.html", disciplina=disciplina,
                               resumo=resumo, itens=itens, json_text=raw,
                               aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/questao/<questao_id>/editar", methods=["GET", "POST"])
    @requer_professor
    def professor_questao_editar(questao_id: str):
        questao = get_pb().buscar_questao(questao_id)
        ativ_id = request.args.get("ativ_id") or request.form.get("ativ_id", "")
        disc_id = questao.get("disciplina", "")
        if ativ_id:
            voltar_url = url_for("professor_questoes_atividade", ativ_id=ativ_id)
        else:
            voltar_url = url_for("professor_banco_questoes", disciplina_id=disc_id)
        if request.method == "GET":
            return render_template(
                "professor/questao_form.html", questao=questao,
                form_action=url_for("professor_questao_editar", questao_id=questao_id),
                voltar_url=voltar_url, ativ_id=ativ_id, disciplina_id=disc_id,
                aluno_nome=session.get("aluno_nome", ""))
        img = request.files.get("imagem")
        img_tuple = (img.filename, img.read(), img.content_type) if img and img.filename else None
        get_pb().atualizar_questao(questao_id, _questao_campos_comuns(request.form), img_tuple)
        return redirect(voltar_url)

    @app.route("/professor/questao/<questao_id>/clonar", methods=["POST"])
    @requer_professor
    def professor_clonar_questao(questao_id: str):
        ativ_id = request.form.get("ativ_id", "")
        questao = get_pb().buscar_questao(questao_id)
        disc_id = questao.get("disciplina", "")
        get_pb().clonar_questao(questao_id)
        if ativ_id:
            return redirect(url_for("professor_questoes_atividade", ativ_id=ativ_id))
        return redirect(url_for("professor_banco_questoes", disciplina_id=disc_id))

    @app.route("/professor/questao/<questao_id>/reclassificar", methods=["POST"])
    @requer_professor
    def professor_reclassificar_questao(questao_id: str):
        nova_disc = request.form.get("disciplina", "")
        novo_assunto = request.form.get("assunto", "")
        get_pb().reclassificar_questao(questao_id, nova_disc, novo_assunto)
        destino = nova_disc or request.form.get("origem_disciplina", "")
        return redirect(url_for("professor_banco_questoes", disciplina_id=destino))

    @app.route("/professor/questao/<questao_id>/excluir", methods=["POST"])
    @requer_professor
    def professor_questao_excluir(questao_id: str):
        ativ_id = request.form.get("ativ_id", "")
        origem_disc = request.form.get("origem_disciplina", "")
        # Cascade manual: remove a referência de todas as atividades que usam a
        # questão antes de apagá-la (cascadeDelete=False é proposital — não
        # queremos apagar a atividade, só limpar o vínculo órfão). Também
        # remove os subitens (alternativas/itens_vf/pares) antes: o PocketBase
        # recusa (400) apagar um registro ainda referenciado por uma relation
        # obrigatória sem cascadeDelete habilitado nela.
        get_pb().remover_questao_de_todas_atividades(questao_id)
        get_pb().apagar_subitens_questao(questao_id)
        try:
            get_pb().excluir_questao(questao_id)
        except Exception as exc:
            log.warning("excluir_questao(%s) falhou mesmo após remover vínculos/subitens: %s",
                       questao_id, exc)
            erro = _erro_http(exc)
            if ativ_id:
                return redirect(url_for("professor_questoes_atividade", ativ_id=ativ_id, erro_exclusao=erro))
            return redirect(url_for("professor_banco_questoes", disciplina_id=origem_disc, erro_exclusao=erro))
        if ativ_id:
            return redirect(url_for("professor_questoes_atividade", ativ_id=ativ_id))
        return redirect(url_for("professor_banco_questoes", disciplina_id=origem_disc))

    @app.route("/professor/disciplina/<disciplina_id>/questoes/excluir-em-massa", methods=["POST"])
    @requer_professor
    def professor_questoes_excluir_em_massa(disciplina_id: str):
        ids = request.form.getlist("questoes")
        falhas = 0
        for qid in ids:
            try:
                get_pb().remover_questao_de_todas_atividades(qid)
                get_pb().apagar_subitens_questao(qid)
                get_pb().excluir_questao(qid)
            except Exception as exc:
                log.warning("excluir_em_massa falhou para %s: %s", qid, exc)
                falhas += 1
        if falhas:
            return redirect(url_for("professor_banco_questoes", disciplina_id=disciplina_id, falhas_exclusao=falhas))
        return redirect(url_for("professor_banco_questoes", disciplina_id=disciplina_id))

    # ── Banco de questões da disciplina ──

    @app.route("/professor/disciplina/<disciplina_id>/banco-questoes")
    @requer_professor
    def professor_banco_questoes(disciplina_id: str):
        disciplina = get_pb().buscar_disciplina(disciplina_id)
        filtros = {c: request.args.get(c, "") for c in ("tipo", "assunto", "dificuldade")}
        questoes = get_pb().listar_questoes_disciplina(disciplina_id, filtros)
        for q in questoes:
            try:
                q["_uso"] = get_pb().contar_uso_questao(q["id"])
            except Exception:
                q["_uso"] = 0
        # lista de assuntos para o filtro (a partir do banco completo, sem filtro)
        if any(filtros.values()):
            todas = get_pb().listar_questoes_disciplina(disciplina_id)
        else:
            todas = questoes
        assuntos = sorted({q.get("assunto", "") for q in todas if q.get("assunto")})
        disciplinas = get_pb().listar_disciplinas()
        return render_template(
            "professor/banco_questoes.html", disciplina=disciplina, questoes=questoes,
            assuntos=assuntos, filtros=filtros, disciplinas=disciplinas,
            aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/atividade/<ativ_id>/selecionar-questoes")
    @requer_professor
    def professor_selecionar_questoes(ativ_id: str):
        ativ = get_pb().buscar_atividade(ativ_id)
        disc_id = ativ.get("disciplina", "")
        filtros = {c: request.args.get(c, "") for c in ("tipo", "assunto", "dificuldade")}
        questoes = get_pb().listar_questoes_disciplina(disc_id, filtros)
        ja_incluidas = set(ativ.get("questoes") or [])
        disponiveis = [q for q in questoes if q["id"] not in ja_incluidas]
        if any(filtros.values()):
            todas = get_pb().listar_questoes_disciplina(disc_id)
        else:
            todas = questoes
        assuntos = sorted({q.get("assunto", "") for q in todas if q.get("assunto")})
        return render_template(
            "professor/selecionar_questoes.html", ativ=ativ, questoes=disponiveis,
            assuntos=assuntos, filtros=filtros, aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/atividade/<ativ_id>/adicionar-questoes", methods=["POST"])
    @requer_professor
    def professor_adicionar_questoes(ativ_id: str):
        ativ = get_pb().buscar_atividade(ativ_id)
        atual = list(ativ.get("questoes") or [])
        for qid in request.form.getlist("questoes"):
            if qid and qid not in atual:
                atual.append(qid)
        get_pb().atualizar_atividade(ativ_id, {"questoes": atual})
        return redirect(url_for("professor_questoes_atividade", ativ_id=ativ_id))

    # ── Banco geral de questões (todas as disciplinas) ──

    @app.route("/professor/banco-questoes")
    @requer_professor
    def professor_banco_geral():
        filtros = {c: request.args.get(c, "") for c in ("disciplina", "tipo", "assunto")}
        questoes = get_pb().listar_questoes(filtros)
        disciplinas = get_pb().listar_disciplinas()
        disc_map = {d["id"]: d.get("nome", "") for d in disciplinas}
        for q in questoes:
            q["_disc_nome"] = disc_map.get(q.get("disciplina", ""), "—")
        # assuntos para o filtro: do conjunto sem filtro de assunto
        if any(filtros.values()):
            todas = get_pb().listar_questoes(
                {"disciplina": filtros.get("disciplina", "")})
        else:
            todas = questoes
        assuntos = sorted({q.get("assunto", "") for q in todas if q.get("assunto")})
        return render_template("professor/banco_geral.html", questoes=questoes,
                               disciplinas=disciplinas, assuntos=assuntos, filtros=filtros,
                               aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/atividade/multidisciplinar", methods=["GET", "POST"])
    @requer_professor
    def professor_atividade_multidisciplinar():
        if request.method == "GET":
            ids = request.args.getlist("questoes")
            questoes = get_pb().listar_questoes_atividade(ids) if ids else []
            disciplinas = get_pb().listar_disciplinas()
            disc_map = {d["id"]: d.get("nome", "") for d in disciplinas}
            # disciplina principal sugerida: a mais frequente entre as selecionadas
            freq: dict[str, int] = {}
            for q in questoes:
                q["_disc_nome"] = disc_map.get(q.get("disciplina", ""), "—")
                did = q.get("disciplina", "")
                if did:
                    freq[did] = freq.get(did, 0) + 1
            sugerida = max(freq, key=freq.get) if freq else ""
            turmas = get_pb().listar_turmas()
            return render_template("professor/atividade_multidisciplinar.html",
                                   questoes=questoes, ids=ids, turmas=turmas,
                                   disciplinas=disciplinas, disciplina_sugerida=sugerida,
                                   aluno_nome=session.get("aluno_nome", ""))
        data = _form_to_atividade(request.form)
        data["questoes"] = request.form.getlist("questoes")
        data["multidisciplinar"] = True
        try:
            get_pb().criar_atividade(data)
        except Exception as exc:
            log.warning("criar_atividade multidisciplinar falhou: %s", exc)
        return redirect(url_for("professor_turma", turma_id=data.get("turma", "")))

    # ── Gestão de turmas ──

    @app.route("/professor/turmas")
    @requer_professor
    def professor_turmas():
        turmas = get_pb().listar_turmas()
        return render_template("professor/turmas.html", turmas=turmas,
                               aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/turma/nova", methods=["GET", "POST"])
    @requer_professor
    def professor_turma_nova():
        if request.method == "GET":
            return render_template("professor/turma_form.html", turma=None,
                                   aluno_nome=session.get("aluno_nome", ""))
        get_pb().criar_turma(_form_to_turma(request.form))
        return redirect(url_for("professor_turmas"))

    @app.route("/professor/turma/<turma_id>/editar", methods=["GET", "POST"])
    @requer_professor
    def professor_turma_editar(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        if request.method == "GET":
            return render_template("professor/turma_form.html", turma=turma,
                                   aluno_nome=session.get("aluno_nome", ""))
        get_pb().atualizar_turma(turma_id, _form_to_turma(request.form))
        return redirect(url_for("professor_turmas"))

    @app.route("/professor/turma/<turma_id>/excluir", methods=["POST"])
    @requer_professor
    def professor_turma_excluir(turma_id: str):
        vinculos = get_pb().contar_vinculos_turma(turma_id)
        if sum(vinculos.values()) > 0:
            turmas = get_pb().listar_turmas()
            return render_template(
                "professor/turmas.html", turmas=turmas, erro_vinculo=vinculos,
                erro_turma_id=turma_id, aluno_nome=session.get("aluno_nome", "")), 422
        get_pb().excluir_turma(turma_id)
        return redirect(url_for("professor_turmas"))

    # ── Gestão de disciplinas ──

    @app.route("/professor/disciplinas")
    @requer_professor
    def professor_disciplinas():
        disciplinas = get_pb().listar_disciplinas()
        return render_template("professor/disciplinas.html", disciplinas=disciplinas,
                               aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/disciplina/nova", methods=["GET", "POST"])
    @requer_professor
    def professor_disciplina_nova():
        if request.method == "GET":
            return render_template("professor/disciplina_form.html", disciplina=None,
                                   aluno_nome=session.get("aluno_nome", ""))
        get_pb().criar_disciplina(_form_to_disciplina(request.form))
        return redirect(url_for("professor_disciplinas"))

    @app.route("/professor/disciplina/<disciplina_id>/editar", methods=["GET", "POST"])
    @requer_professor
    def professor_disciplina_editar(disciplina_id: str):
        disciplina = get_pb().buscar_disciplina(disciplina_id)
        if request.method == "GET":
            return render_template("professor/disciplina_form.html", disciplina=disciplina,
                                   aluno_nome=session.get("aluno_nome", ""))
        get_pb().atualizar_disciplina(disciplina_id, _form_to_disciplina(request.form))
        return redirect(url_for("professor_disciplinas"))

    @app.route("/professor/disciplina/<disciplina_id>/excluir", methods=["POST"])
    @requer_professor
    def professor_disciplina_excluir(disciplina_id: str):
        vinculos = get_pb().contar_vinculos_disciplina(disciplina_id)
        if sum(vinculos.values()) > 0:
            disciplinas = get_pb().listar_disciplinas()
            return render_template(
                "professor/disciplinas.html", disciplinas=disciplinas, erro_vinculo=vinculos,
                erro_disciplina_id=disciplina_id, aluno_nome=session.get("aluno_nome", "")), 422
        get_pb().excluir_disciplina(disciplina_id)
        return redirect(url_for("professor_disciplinas"))

    # ── Vínculo turma ↔ disciplina ──

    @app.route("/professor/turma/<turma_id>/disciplinas")
    @requer_professor
    def professor_turma_disciplinas(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        vinculos = get_pb().listar_turma_disciplinas(turma_id)
        vinculadas_ids = {(v.get("expand") or {}).get("disciplina", {}).get("id")
                          or v.get("disciplina") for v in vinculos}
        disponiveis = [d for d in get_pb().listar_disciplinas() if d["id"] not in vinculadas_ids]
        return render_template("professor/turma_disciplinas.html", turma=turma,
                               vinculos=vinculos, disponiveis=disponiveis,
                               aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/turma/<turma_id>/disciplinas/vincular", methods=["POST"])
    @requer_professor
    def professor_vincular_disciplina(turma_id: str):
        disc_id = request.form.get("disciplina", "")
        if disc_id:
            get_pb().vincular_disciplina(
                turma_id, disc_id,
                request.form.get("professor", ""), request.form.get("semestre", ""))
        return redirect(url_for("professor_turma_disciplinas", turma_id=turma_id))

    @app.route("/professor/turma/<turma_id>/disciplinas/desvincular/<vinculo_id>", methods=["POST"])
    @requer_professor
    def professor_desvincular_disciplina(turma_id: str, vinculo_id: str):
        get_pb().desvincular_disciplina(vinculo_id)
        return redirect(url_for("professor_turma_disciplinas", turma_id=turma_id))

    # ── Banco de materiais (por disciplina) ──

    @app.route("/professor/disciplina/<disciplina_id>/banco-materiais")
    @requer_professor
    def professor_banco_materiais(disciplina_id: str):
        disciplina = get_pb().buscar_disciplina(disciplina_id)
        filtros = {c: request.args.get(c, "") for c in ("tipo", "assunto")}
        materiais = get_pb().listar_materiais_disciplina(disciplina_id, filtros)
        for m in materiais:
            try:
                m["_uso"] = get_pb().contar_uso_material(m["id"])
            except Exception:
                m["_uso"] = 0
        todos = materiais if not any(filtros.values()) else \
            get_pb().listar_materiais_disciplina(disciplina_id)
        assuntos = sorted({m.get("assunto", "") for m in todos if m.get("assunto")})
        disciplinas = get_pb().listar_disciplinas()
        return render_template("professor/banco_materiais.html", disciplina=disciplina,
                               materiais=materiais, assuntos=assuntos, filtros=filtros,
                               disciplinas=disciplinas, aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/material/novo", methods=["GET", "POST"])
    @requer_professor
    def professor_material_novo():
        disciplina_id = request.values.get("disciplina", "")
        turma_id = request.values.get("turma", "")
        if request.method == "GET":
            # Quando a disciplina não vem fixa, oferece um seletor. Vindo de uma
            # turma, restringe às disciplinas da turma; senão, todas.
            disciplinas_opcoes = []
            if not disciplina_id:
                if turma_id:
                    disciplinas_opcoes = _disciplinas_da_turma(turma_id)
                if not disciplinas_opcoes:
                    disciplinas_opcoes = get_pb().listar_disciplinas()
            voltar_url = (url_for("professor_turma_materiais", turma_id=turma_id) if turma_id
                          else url_for("professor_banco_materiais", disciplina_id=disciplina_id))
            return render_template(
                "professor/material_form.html", material=None, disciplina_id=disciplina_id,
                turma_id=turma_id, disciplinas_opcoes=disciplinas_opcoes,
                form_action=url_for("professor_material_novo"),
                voltar_url=voltar_url, aluno_nome=session.get("aluno_nome", ""))
        disciplina_id = request.form.get("disciplina", "") or disciplina_id
        arq = request.files.get("arquivo")
        arq_tuple = (arq.filename, arq.read(), arq.content_type) if arq and arq.filename else None
        material = get_pb().criar_material({
            **_material_campos_comuns(request.form),
            "tipo": request.form.get("tipo", "link"),
            "disciplina": disciplina_id,
            "ativo": True,
        }, arq_tuple)
        # Criado a partir de uma turma: já vincula o material à turma.
        if turma_id:
            try:
                get_pb().adicionar_material_turma(turma_id, material["id"])
            except Exception as exc:
                log.warning("adicionar_material_turma falhou: %s", exc)
            return redirect(url_for("professor_turma_materiais", turma_id=turma_id))
        return redirect(url_for("professor_banco_materiais", disciplina_id=disciplina_id))

    @app.route("/professor/material/<material_id>/editar", methods=["GET", "POST"])
    @requer_professor
    def professor_material_editar(material_id: str):
        material = get_pb().buscar_material(material_id)
        disc_id = material.get("disciplina", "")
        voltar_url = url_for("professor_banco_materiais", disciplina_id=disc_id)
        if request.method == "GET":
            return render_template(
                "professor/material_form.html", material=material, disciplina_id=disc_id,
                form_action=url_for("professor_material_editar", material_id=material_id),
                voltar_url=voltar_url, aluno_nome=session.get("aluno_nome", ""))
        arq = request.files.get("arquivo")
        arq_tuple = (arq.filename, arq.read(), arq.content_type) if arq and arq.filename else None
        get_pb().atualizar_material(material_id, _material_campos_comuns(request.form), arq_tuple)
        return redirect(voltar_url)

    @app.route("/professor/material/<material_id>/clonar", methods=["POST"])
    @requer_professor
    def professor_clonar_material(material_id: str):
        material = get_pb().buscar_material(material_id)
        get_pb().clonar_material(material_id)
        return redirect(url_for("professor_banco_materiais",
                                disciplina_id=material.get("disciplina", "")))

    @app.route("/professor/material/<material_id>/reclassificar", methods=["POST"])
    @requer_professor
    def professor_reclassificar_material(material_id: str):
        nova_disc = request.form.get("disciplina", "")
        novo_assunto = request.form.get("assunto", "")
        get_pb().reclassificar_material(material_id, nova_disc, novo_assunto)
        destino = nova_disc or request.form.get("origem_disciplina", "")
        return redirect(url_for("professor_banco_materiais", disciplina_id=destino))

    @app.route("/professor/material/<material_id>/excluir", methods=["POST"])
    @requer_professor
    def professor_material_excluir(material_id: str):
        origem_disc = request.form.get("origem_disciplina", "")
        # cascade: limpa vínculos turma_materiais antes de apagar
        get_pb().remover_material_de_todas_turmas(material_id)
        get_pb().excluir_material(material_id)
        return redirect(url_for("professor_banco_materiais", disciplina_id=origem_disc))

    # ── Materiais de uma turma (vínculo turma_materiais) ──

    @app.route("/professor/turma/<turma_id>/materiais")
    @requer_professor
    def professor_turma_materiais(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        vinculos = get_pb().listar_turma_materiais(turma_id)
        return render_template("professor/turma_materiais.html", turma=turma,
                               vinculos=vinculos, aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/turma/<turma_id>/materiais/selecionar")
    @requer_professor
    def professor_selecionar_materiais(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        disc_id = request.args.get("disciplina", "")
        filtros = {c: request.args.get(c, "") for c in ("tipo", "assunto")}
        ja_ids = {(v.get("expand") or {}).get("material", {}).get("id") or v.get("material")
                  for v in get_pb().listar_turma_materiais(turma_id)}
        materiais = []
        assuntos = []
        if disc_id:
            todos = get_pb().listar_materiais_disciplina(disc_id, filtros)
            materiais = [m for m in todos if m["id"] not in ja_ids]
            base = todos if not any(filtros.values()) else get_pb().listar_materiais_disciplina(disc_id)
            assuntos = sorted({m.get("assunto", "") for m in base if m.get("assunto")})
        disciplinas = get_pb().listar_disciplinas()
        return render_template("professor/selecionar_materiais.html", turma=turma,
                               materiais=materiais, disciplinas=disciplinas, disc_id=disc_id,
                               assuntos=assuntos, filtros=filtros,
                               aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/turma/<turma_id>/materiais/adicionar", methods=["POST"])
    @requer_professor
    def professor_adicionar_materiais(turma_id: str):
        for mid in request.form.getlist("materiais"):
            if mid and not get_pb().material_ja_na_turma(turma_id, mid):
                get_pb().adicionar_material_turma(turma_id, mid)
        return redirect(url_for("professor_turma_materiais", turma_id=turma_id))

    @app.route("/professor/turma/<turma_id>/materiais/remover/<vinculo_id>", methods=["POST"])
    @requer_professor
    def professor_remover_material_turma(turma_id: str, vinculo_id: str):
        get_pb().remover_material_turma(vinculo_id)
        return redirect(url_for("professor_turma_materiais", turma_id=turma_id))

    # ── Boletim ──

    def _dados_boletim(turma_id: str) -> dict | None:
        """Carrega o boletim da turma e calcula o resultado de todos os alunos."""
        boletim = get_pb().buscar_boletim_turma(turma_id)
        if not boletim:
            return None
        unidades = get_pb().listar_unidades_boletim(boletim["id"])
        rec_finais = get_pb().listar_rec_finais(boletim["id"])
        atividades = get_pb().listar_todas_atividades_turma(turma_id)
        atividades_map = {a["id"]: {"valor_total": a.get("valor_total")} for a in atividades}
        todos_tentativas: list = []
        for a in atividades:
            try:
                todos_tentativas.extend(get_pb().listar_tentativas_atividade(a["id"]))
            except Exception:
                pass
        alunos_map: dict[str, dict] = {}
        for t in todos_tentativas:
            alid = t.get("aluno_id")
            if alid and alid not in alunos_map:
                alunos_map[alid] = {"aluno_id": alid, "nome": t.get("aluno_nome", alid)}
        alunos = sorted(alunos_map.values(), key=lambda a: a["nome"])
        disc_ids = {u.get("disciplina") for u in unidades}
        disciplinas = [d for d in get_pb().listar_disciplinas() if d["id"] in disc_ids]
        resultado = calcular_boletim_turma(boletim, unidades, rec_finais, todos_tentativas,
                                           alunos, disciplinas, atividades_map)
        return {"boletim": boletim, "unidades": unidades, "rec_finais": rec_finais,
                "disciplinas": disciplinas, "alunos": alunos, "resultado": resultado,
                "atividades": atividades}

    @app.route("/professor/turma/<turma_id>/boletim", methods=["GET", "POST"])
    @requer_professor
    def professor_boletim_config(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        boletim = get_pb().buscar_boletim_turma(turma_id)
        if request.method == "GET":
            return render_template("professor/boletim/configurar.html", turma=turma,
                                   boletim=boletim, aluno_nome=session.get("aluno_nome", ""))
        data = _form_to_boletim(request.form, turma_id)
        if boletim:
            get_pb().atualizar_boletim(boletim["id"], data)
        else:
            get_pb().criar_boletim(data)
        return redirect(url_for("professor_boletim_unidades", turma_id=turma_id))

    @app.route("/professor/turma/<turma_id>/boletim/ativar", methods=["POST"])
    @requer_professor
    def professor_boletim_ativar(turma_id: str):
        b = get_pb().buscar_boletim_turma(turma_id)
        if b:
            get_pb().atualizar_boletim(b["id"], {"ativo": not b.get("ativo")})
        return redirect(url_for("professor_boletim_config", turma_id=turma_id))

    @app.route("/professor/turma/<turma_id>/boletim/liberar", methods=["POST"])
    @requer_professor
    def professor_boletim_liberar(turma_id: str):
        b = get_pb().buscar_boletim_turma(turma_id)
        if b:
            get_pb().atualizar_boletim(b["id"], {"liberado": not b.get("liberado")})
        return redirect(url_for("professor_boletim_config", turma_id=turma_id))

    @app.route("/professor/turma/<turma_id>/boletim/unidades")
    @requer_professor
    def professor_boletim_unidades(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        boletim = get_pb().buscar_boletim_turma(turma_id)
        if not boletim:
            return redirect(url_for("professor_boletim_config", turma_id=turma_id))
        unidades = get_pb().listar_unidades_boletim(boletim["id"])
        rec_finais = get_pb().listar_rec_finais(boletim["id"])
        atividades = get_pb().listar_todas_atividades_turma(turma_id)
        disc_ids = {(a.get("expand") or {}).get("disciplina", {}).get("id") for a in atividades}
        disciplinas = [d for d in get_pb().listar_disciplinas() if d["id"] in disc_ids]
        return render_template("professor/boletim/unidades.html", turma=turma, boletim=boletim,
                               unidades=unidades, rec_finais=rec_finais, atividades=atividades,
                               disciplinas=disciplinas, aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/turma/<turma_id>/boletim/unidade/nova", methods=["POST"])
    @requer_professor
    def professor_boletim_unidade_nova(turma_id: str):
        boletim = get_pb().buscar_boletim_turma(turma_id)
        if boletim:
            get_pb().criar_unidade(_form_to_unidade(request.form, boletim["id"]))
        return redirect(url_for("professor_boletim_unidades", turma_id=turma_id))

    @app.route("/professor/turma/<turma_id>/boletim/unidade/<uid>/editar", methods=["POST"])
    @requer_professor
    def professor_boletim_unidade_editar(turma_id: str, uid: str):
        boletim = get_pb().buscar_boletim_turma(turma_id)
        if boletim:
            get_pb().atualizar_unidade(uid, _form_to_unidade(request.form, boletim["id"]))
        return redirect(url_for("professor_boletim_unidades", turma_id=turma_id))

    @app.route("/professor/turma/<turma_id>/boletim/unidade/<uid>/excluir", methods=["POST"])
    @requer_professor
    def professor_boletim_unidade_excluir(turma_id: str, uid: str):
        get_pb().excluir_unidade(uid)
        return redirect(url_for("professor_boletim_unidades", turma_id=turma_id))

    @app.route("/professor/turma/<turma_id>/boletim/rec-final", methods=["POST"])
    @requer_professor
    def professor_boletim_rec_final(turma_id: str):
        boletim = get_pb().buscar_boletim_turma(turma_id)
        if boletim:
            rec_manual = (request.form.get("rec_nota_manual") or "").strip()
            get_pb().salvar_rec_final({
                "boletim": boletim["id"],
                "disciplina": request.form.get("disciplina", ""),
                "rec_atividade": request.form.get("rec_atividade", ""),
                "rec_nota_manual": float(rec_manual) if rec_manual else None,
            })
        return redirect(url_for("professor_boletim_unidades", turma_id=turma_id))

    @app.route("/professor/turma/<turma_id>/boletim/notas")
    @requer_professor
    def professor_boletim_notas(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        dados = _dados_boletim(turma_id)
        if not dados:
            return redirect(url_for("professor_boletim_config", turma_id=turma_id))
        # nº de unidades por disciplina (para o cabeçalho do mapa de calor)
        unidades_por_disc: dict[str, list] = {}
        for u in sorted(dados["unidades"], key=lambda x: x.get("numero", 0)):
            unidades_por_disc.setdefault(u.get("disciplina"), []).append(u)
        return render_template("professor/boletim/notas.html", turma=turma, modo="notas",
                               unidades_por_disc=unidades_por_disc, aluno_nome=session.get("aluno_nome", ""),
                               **dados)

    @app.route("/professor/turma/<turma_id>/boletim/relatorio")
    @requer_professor
    def professor_boletim_relatorio(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        dados = _dados_boletim(turma_id)
        if not dados:
            return redirect(url_for("professor_boletim_config", turma_id=turma_id))
        return render_template("professor/boletim/relatorio.html", turma=turma,
                               aluno_nome=session.get("aluno_nome", ""), **dados)

    @app.route("/professor/aluno/<aluno_id>/boletim/<turma_id>")
    @requer_professor
    def professor_boletim_aluno(aluno_id: str, turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        dados = _dados_boletim(turma_id)
        if not dados:
            return redirect(url_for("professor_boletim_config", turma_id=turma_id))
        res = dados["resultado"].get(aluno_id)
        if res is None:
            res = calcular_boletim_aluno(dados["boletim"], dados["unidades"],
                                         dados["rec_finais"], {}, dados["disciplinas"])
        nome = next((a["nome"] for a in dados["alunos"] if a["aluno_id"] == aluno_id), aluno_id)
        return render_template("aluno/boletim.html", turma=turma, boletim=dados["boletim"],
                               resultado=res, aluno_nome_boletim=nome, modo_professor=True,
                               aluno_nome=session.get("aluno_nome", ""))

    @app.route("/aluno/boletim/<turma_id>")
    @requer_login
    def aluno_boletim(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        boletim = get_pb().buscar_boletim_turma(turma_id)
        if not boletim or not boletim.get("liberado"):
            return render_template("aluno/boletim.html", turma=turma, boletim=boletim,
                                   indisponivel=True,
                                   aluno_nome=session.get("aluno_nome", "")), 403
        dados = _dados_boletim(turma_id)
        aluno_id = session.get("aluno_id", "")
        res = dados["resultado"].get(aluno_id)
        if res is None:
            res = calcular_boletim_aluno(dados["boletim"], dados["unidades"],
                                         dados["rec_finais"], {}, dados["disciplinas"])
        return render_template("aluno/boletim.html", turma=turma, boletim=boletim,
                               resultado=res, aluno_nome_boletim=session.get("aluno_nome", ""),
                               aluno_nome=session.get("aluno_nome", ""))

    # ── Redefinição de senha (público) ──

    @app.route("/redefinir-senha/<token>", methods=["GET", "POST"])
    def redefinir_senha(token: str):
        registro = get_pb().buscar_token_senha(token)
        if not registro:
            return render_template("cadastro/redefinir_senha.html", token=token,
                                   invalido=True), 410
        if request.method == "GET":
            return render_template("cadastro/redefinir_senha.html", token=token)
        nova = request.form.get("senha", "")
        confirmar = request.form.get("senha_confirmar", "")
        if len(nova) < 6:
            return render_template("cadastro/redefinir_senha.html", token=token,
                                   erro="A senha deve ter pelo menos 6 caracteres.")
        if nova != confirmar:
            return render_template("cadastro/redefinir_senha.html", token=token,
                                   erro="As senhas não coincidem.")
        try:
            get_pb().redefinir_senha_aluno(registro["aluno_id"], nova)
            get_pb().invalidar_token_senha(registro["id"])
        except Exception as exc:
            log.warning("redefinir_senha falhou: %s", exc)
            return render_template("cadastro/redefinir_senha.html", token=token,
                                   erro="Não foi possível alterar a senha. Tente novamente.")
        return render_template("cadastro/redefinir_senha.html", token=token, sucesso=True)

    # ── Ações de aluno (professor, via HTMX) ──

    @app.route("/professor/aluno/<aluno_id>/redefinir-senha", methods=["POST"])
    @requer_professor
    def professor_aluno_redefinir_senha(aluno_id: str):
        try:
            user = get_pb().buscar_user(aluno_id)
            token = secrets.token_urlsafe(32)
            expira = _pb_datetime(datetime.now(timezone.utc) + timedelta(hours=24))
            get_pb().criar_token_senha(aluno_id, token, expira)
            link = f"{_portal_url()}/redefinir-senha/{token}"
            ok = email_redefinir_senha(user.get("email", ""), user.get("name", ""), link)
        except Exception as exc:
            log.warning("professor_aluno_redefinir_senha falhou: %s", exc)
            ok = False
        return _feedback_aluno_acao(ok, "Link de redefinição enviado", "Falha no envio")

    @app.route("/professor/aluno/<aluno_id>/reenviar-boas-vindas", methods=["POST"])
    @requer_professor
    def professor_aluno_reenviar(aluno_id: str):
        turma_nome = request.form.get("turma_nome", "")
        try:
            user = get_pb().buscar_user(aluno_id)
            nova_senha = _senha_temporaria()
            get_pb().redefinir_senha_aluno(aluno_id, nova_senha)
            ok = email_boas_vindas(user.get("email", ""), user.get("name", ""),
                                   nova_senha, turma_nome, _portal_url())
        except Exception as exc:
            log.warning("professor_aluno_reenviar falhou: %s", exc)
            ok = False
        return _feedback_aluno_acao(ok, "Email enviado", "Falha no envio")

    def _feedback_aluno_acao(ok: bool, msg_ok: str, msg_falha: str):
        cor = "var(--sucesso)" if ok else "var(--erro)"
        icone = "✓" if ok else "✗"
        texto = msg_ok if ok else msg_falha
        return (f'<span class="aluno-acao-feedback" style="color:{cor};font-size:.8rem;">'
                f'{icone} {texto}</span>')

    # ── Gestão de alunos da turma (professor) ──

    @app.route("/professor/turma/<turma_id>/alunos")
    @requer_professor
    def professor_alunos(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        try:
            matriculas = get_pb().listar_alunos_turma(turma_id)
        except Exception:
            matriculas = []  # collection 'matriculas' ausente (pré-migração)
        try:
            formulario = get_pb().buscar_formulario_turma(turma_id)
        except Exception:
            formulario = None
        return render_template("professor/alunos.html", turma=turma, matriculas=matriculas,
                               formulario=formulario, portal_url=_portal_url(),
                               aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/turma/<turma_id>/alunos/novo", methods=["GET", "POST"])
    @requer_professor
    def professor_aluno_novo(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        if request.method == "GET":
            return render_template("professor/aluno_form.html", turma=turma,
                                   aluno_nome=session.get("aluno_nome", ""))
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        matricula = request.form.get("matricula", "").strip()
        enviar = "enviar_email" in request.form
        if not (nome and email and senha):
            return render_template("professor/aluno_form.html", turma=turma,
                                   erro="Nome, email e senha são obrigatórios.",
                                   dados={"nome": nome, "email": email, "whatsapp": whatsapp,
                                          "matricula": matricula},
                                   aluno_nome=session.get("aluno_nome", "")), 422
        try:
            user = get_pb().criar_user_aluno(nome, email, senha, matricula)
            get_pb().criar_matricula(user["id"], turma_id, origem="manual", whatsapp=whatsapp)
        except Exception as exc:
            log.warning("criar_user_aluno falhou: %s", exc)
            return render_template("professor/aluno_form.html", turma=turma,
                                   erro="Não foi possível criar o aluno (email já usado?).",
                                   dados={"nome": nome, "email": email, "whatsapp": whatsapp,
                                          "matricula": matricula},
                                   aluno_nome=session.get("aluno_nome", "")), 422
        if enviar:
            try:
                email_boas_vindas(email, nome, senha, turma.get("nome", ""), _portal_url())
            except Exception as exc:
                log.warning("email_boas_vindas falhou: %s", exc)
        return redirect(url_for("professor_alunos", turma_id=turma_id))

    @app.route("/professor/aluno/<aluno_id>/matricula", methods=["POST"])
    @requer_professor
    def professor_aluno_matricula(aluno_id: str):
        matricula = request.form.get("matricula", "").strip()
        try:
            get_pb().atualizar_user(aluno_id, {"matricula": matricula})
        except Exception as exc:
            log.warning("atualizar matricula falhou: %s", exc)
        return render_template("professor/components/_matricula_cell.html",
                               aluno_id=aluno_id, matricula=matricula)

    # ── Formulário público de cadastro (professor) ──

    @app.route("/professor/turma/<turma_id>/formulario/criar", methods=["POST"])
    @requer_professor
    def professor_formulario_criar(turma_id: str):
        if not get_pb().buscar_formulario_turma(turma_id):
            token = secrets.token_urlsafe(32)
            get_pb().criar_formulario_cadastro(turma_id, token)
        return redirect(url_for("professor_alunos", turma_id=turma_id))

    @app.route("/professor/turma/<turma_id>/formulario/toggle", methods=["POST"])
    @requer_professor
    def professor_formulario_toggle(turma_id: str):
        form = get_pb().buscar_formulario_turma(turma_id)
        if form:
            form = get_pb().toggle_formulario(form["id"], not form.get("ativo"))
        return render_template("professor/components/_formulario_box.html",
                               turma_id=turma_id, formulario=form, portal_url=_portal_url())

    @app.route("/professor/turma/<turma_id>/formulario/relatorio")
    @requer_professor
    def professor_formulario_relatorio(turma_id: str):
        turma = get_pb().buscar_turma(turma_id)
        try:
            matriculas = [m for m in get_pb().listar_alunos_turma(turma_id)
                          if m.get("origem") == "formulario"]
        except Exception:
            matriculas = []
        return render_template("professor/formulario_relatorio.html", turma=turma,
                               matriculas=matriculas, aluno_nome=session.get("aluno_nome", ""))

    @app.route("/professor/turma/<turma_id>/formulario/relatorio.csv")
    @requer_professor
    def professor_formulario_relatorio_csv(turma_id: str):
        try:
            matriculas = [m for m in get_pb().listar_alunos_turma(turma_id)
                          if m.get("origem") == "formulario"]
        except Exception:
            matriculas = []
        linhas = ["nome,email,matricula,whatsapp,cadastrado_em"]
        for m in matriculas:
            al = (m.get("expand") or {}).get("aluno") or {}
            campos = [al.get("name", ""), al.get("email", ""), al.get("matricula", ""),
                      m.get("whatsapp", ""), m.get("created", "")]
            linhas.append(",".join('"' + str(c).replace('"', '""') + '"' for c in campos))
        csv = "\n".join(linhas)
        r = make_response(csv)
        r.headers["Content-Type"] = "text/csv; charset=utf-8"
        r.headers["Content-Disposition"] = f'attachment; filename="cadastros_{turma_id}.csv"'
        return r

    # ── Cadastro público via link de convite ──

    @app.route("/cadastro/<token>", methods=["GET", "POST"])
    def cadastro_publico(token: str):
        form = get_pb().buscar_formulario_por_token(token)
        if not form:
            return render_template("cadastro/inativo.html", nao_encontrado=True), 404
        if not form.get("ativo"):
            return render_template("cadastro/inativo.html")
        turma = (form.get("expand") or {}).get("turma") or get_pb().buscar_turma(form.get("turma", ""))
        if request.method == "GET":
            return render_template("cadastro/formulario.html", token=token, turma=turma)

        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "")
        confirmar = request.form.get("senha_confirmar", "")
        whatsapp = request.form.get("whatsapp", "").strip()

        def _erro(msg):
            return render_template("cadastro/formulario.html", token=token, turma=turma,
                                   erro=msg, dados={"nome": nome, "email": email, "whatsapp": whatsapp})

        if not (nome and email and senha):
            return _erro("Preencha nome, email e senha."), 422
        if len(senha) < 6:
            return _erro("A senha deve ter pelo menos 6 caracteres."), 422
        if senha != confirmar:
            return _erro("As senhas não coincidem."), 422
        try:
            user = get_pb().criar_user_aluno(nome, email, senha)
        except Exception:
            return _erro("Este email já possui uma conta."), 422
        try:
            get_pb().criar_matricula(user["id"], form.get("turma", ""),
                                     origem="formulario", whatsapp=whatsapp)
        except Exception as exc:
            log.warning("criar_matricula (formulario) falhou: %s", exc)
        # login automático
        try:
            dados = get_pb().login_aluno(email, senha)
            session["token"] = dados["token"]
            session["aluno_id"] = dados["record"]["id"]
            session["aluno_nome"] = dados["record"].get("name", nome)
            session["role"] = dados["record"].get("role", "aluno")
            session["ultimo_acesso"] = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            log.warning("login automático pós-cadastro falhou: %s", exc)
        # email best-effort
        try:
            email_boas_vindas(email, nome, senha, turma.get("nome", "") if turma else "", _portal_url())
        except Exception as exc:
            log.warning("email_boas_vindas (formulario) falhou: %s", exc)
        return redirect(url_for("index"))

    # ------------------------------------------------------------------
    # Status de tentativas (aluno)

    @app.route("/aluno/atividade/<ativ_id>/status")
    @requer_login
    def status_atividade(ativ_id: str):
        aluno_id = session.get("aluno_id", "")
        ativ = get_pb().buscar_atividade(ativ_id)
        max_tent = int(ativ.get("max_tentativas", 0) or 0)
        return get_pb().status_atividade_aluno(ativ_id, aluno_id, max_tent)

    @app.route("/professor/atividade/<ativ_id>/liberar-nota/<tentativa_id>", methods=["POST"])
    @requer_login
    def liberar_nota_rota(ativ_id: str, tentativa_id: str):
        get_pb().liberar_nota(tentativa_id)
        return {"ok": True}

    @app.route("/professor/atividade/<ativ_id>/notas-abertas")
    @requer_login
    def professor_notas_abertas(ativ_id: str):
        ativ = get_pb().buscar_atividade(ativ_id)
        tentativas_raw = get_pb().listar_tentativas_para_avaliar(ativ_id)
        tentativas_detalhes = []
        for tent in tentativas_raw:
            respostas = get_pb().listar_respostas_tentativa(tent["id"])
            abertas = [r for r in respostas if r.get("tipo_questao") == "aberta"]
            for r in abertas:
                try:
                    q = get_pb().buscar_questao(r.get("questao", ""))
                    r["_questao"] = q
                    r["_peso"] = float(q.get("peso") or 1)
                except Exception:
                    r["_questao"] = {}
                    r["_peso"] = 1.0
            tentativas_detalhes.append({"tentativa": tent, "abertas": abertas})
        return render_template(
            "professor/notas_abertas.html",
            atividade=ativ,
            tentativas=tentativas_detalhes,
            aluno_nome=session.get("aluno_nome", ""),
        )

    @app.route("/professor/questao-aberta/<tentativa_id>/avaliar", methods=["POST"])
    @requer_login
    def professor_avaliar_aberta(tentativa_id: str):
        ativ_id = request.form.get("ativ_id", "")
        respostas = get_pb().listar_respostas_tentativa(tentativa_id)
        for r in respostas:
            if r.get("tipo_questao") != "aberta":
                continue
            record_id = r["id"]
            nota_key = f"nota_{record_id}"
            coment_key = f"comentario_{record_id}"
            if nota_key not in request.form:
                continue
            try:
                questao = get_pb().buscar_questao(r.get("questao", ""))
                peso = float(questao.get("peso") or 1)
                nota_val = min(max(float(request.form[nota_key] or 0), 0.0), peso)
                comentario = request.form.get(coment_key, "")
                get_pb().avaliar_questao_aberta(record_id, nota_val, peso, comentario)
            except Exception as exc:
                log.warning("avaliar_questao_aberta falhou: %s", exc)

        try:
            ativ = get_pb().buscar_atividade(ativ_id)
            respostas_atualizadas = get_pb().listar_respostas_tentativa(tentativa_id)
            respostas_com_peso = []
            for r in respostas_atualizadas:
                try:
                    q = get_pb().buscar_questao(r.get("questao", ""))
                    peso = float(q.get("peso") or 1)
                except Exception:
                    peso = 1.0
                respostas_com_peso.append({**r, "_peso": peso})
            nota_final = calcular_nota_final(respostas_com_peso, ativ)
            if nota_final is not None:
                get_pb().patch_tentativa_nota_final(tentativa_id, nota_final)
        except Exception as exc:
            log.warning("recalcular nota_final falhou: %s", exc)

        get_pb().liberar_nota(tentativa_id)
        return redirect(url_for("professor_notas_abertas", ativ_id=ativ_id))

    # ------------------------------------------------------------------
    # Histórico e revisão do aluno

    @app.route("/aluno/historico")
    @requer_login
    def historico_aluno():
        aluno_id = session.get("aluno_id", "")
        tentativas = get_pb().listar_historico_aluno(aluno_id)

        ativ_cache: dict[str, dict] = {}
        for t in tentativas:
            ativ_id = t.get("disciplina", "")
            if ativ_id and ativ_id not in ativ_cache:
                try:
                    ativ_cache[ativ_id] = get_pb().buscar_atividade_expandido(ativ_id)
                except Exception:
                    ativ_cache[ativ_id] = {"id": ativ_id, "titulo": "Atividade", "expand": {}}

        grupos: dict[str, dict] = {}
        for t in tentativas:
            ativ_id = t.get("disciplina", "")
            ativ = ativ_cache.get(ativ_id, {})
            disc = (ativ.get("expand") or {}).get("disciplina") or {"id": "_", "nome": "Outras"}
            disc_id = disc.get("id", "_")
            if disc_id not in grupos:
                grupos[disc_id] = {"disc": disc, "atividades": {}}
            if ativ_id not in grupos[disc_id]["atividades"]:
                grupos[disc_id]["atividades"][ativ_id] = {"ativ": ativ, "tentativas": []}
            grupos[disc_id]["atividades"][ativ_id]["tentativas"].append(t)

        historico = [
            {
                "disc": g["disc"],
                "atividades": list(g["atividades"].values()),
            }
            for g in grupos.values()
        ]
        return render_template(
            "aluno/historico.html",
            historico=historico,
            aluno_nome=session.get("aluno_nome", ""),
        )

    @app.route("/aluno/atividade/<ativ_id>/revisao/<tentativa_id>")
    @requer_login
    def revisao_atividade(ativ_id: str, tentativa_id: str):
        aluno_id = session.get("aluno_id", "")
        ativ = get_pb().buscar_atividade(ativ_id)

        if not ativ.get("exibir_feedback_pos", True):
            return render_template(
                "aluno/revisao.html",
                bloqueado=True,
                atividade=ativ,
                aluno_nome=session.get("aluno_nome", ""),
            ), 403

        try:
            tentativa = get_pb().buscar_tentativa(tentativa_id)
        except Exception:
            return redirect(url_for("index"))

        if tentativa.get("aluno_id") and tentativa.get("aluno_id") != aluno_id:
            return redirect(url_for("index"))

        respostas_list = get_pb().listar_respostas_tentativa(tentativa_id)
        respostas_por_questao = {r["questao"]: r for r in respostas_list if r.get("questao")}

        questoes_revisao = []
        for qid in ativ.get("questoes", []):
            try:
                q = get_pb().buscar_questao(qid)
            except Exception:
                continue
            questoes_revisao.append({
                "questao": q,
                "resposta": respostas_por_questao.get(qid, {}),
            })

        valor_total = ativ.get("valor_total") or None
        if valor_total and questoes_revisao:
            soma_pesos = sum(float(item["questao"].get("peso") or 1) for item in questoes_revisao)
            valor_ponto = float(valor_total) / soma_pesos if soma_pesos > 0 else None
            if valor_ponto:
                for item in questoes_revisao:
                    peso = float(item["questao"].get("peso") or 1)
                    r = item["resposta"]
                    raw = r.get("score_raw", 0) or 0
                    mx = r.get("score_max", 0) or 0
                    item["_peso"] = peso
                    item["_pts"] = round((raw / mx) * peso * valor_ponto, 2) if mx > 0 else 0.0

        return render_template(
            "aluno/revisao.html",
            bloqueado=False,
            atividade=ativ,
            tentativa=tentativa,
            questoes_revisao=questoes_revisao,
            aluno_nome=session.get("aluno_nome", ""),
            valor_total=valor_total,
        )

    # ------------------------------------------------------------------
    # Relatórios

    @app.route("/relatorio/turma/<turma_id>")
    @requer_login
    def relatorio_turma(turma_id: str):
        return render_template("relatorio/turma.html", turma_id=turma_id)

    @app.route("/relatorio/aluno/<aluno_id>")
    @requer_login
    def relatorio_aluno(aluno_id: str):
        return render_template("relatorio/aluno.html", aluno_id=aluno_id)

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=8091)
