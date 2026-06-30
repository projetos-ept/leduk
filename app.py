import logging
import os
import re
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, make_response, redirect, render_template, request, session, url_for

from pb import PocketBaseClient
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
                "correta": form.get(f"vf_ok_{i}") == "V",
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

        logado = bool(session.get("token"))
        aluno_id = session.get("aluno_id", "")
        if logado:
            atividades = get_pb().listar_atividades_por_disciplina(turma_id, disciplina_id)
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
            "components/_feedback.html", resultado=resultado, questao=questao, ativ_id=ativ_id
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
        # queremos apagar a atividade, só limpar o vínculo órfão).
        get_pb().remover_questao_de_todas_atividades(questao_id)
        get_pb().excluir_questao(questao_id)
        if ativ_id:
            return redirect(url_for("professor_questoes_atividade", ativ_id=ativ_id))
        return redirect(url_for("professor_banco_questoes", disciplina_id=origem_disc))

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
