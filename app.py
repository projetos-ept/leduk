import logging
import os
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, redirect, render_template, request, session, url_for

from pb import PocketBaseClient
from questao import validar_associativa, validar_mc, validar_vf

log = logging.getLogger(__name__)

_TEMPLATE_MAP = {
    "mc4": "components/_questao_mc.html",
    "mc5": "components/_questao_mc.html",
    "vf": "components/_questao_vf.html",
    "associativa": "components/_questao_assoc.html",
}


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

    def requer_login(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not app.config.get("LOGIN_REQUIRED", True):
                return f(*args, **kwargs)
            if not session.get("token"):
                return redirect(url_for("login"))
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
            dados = pb.login_aluno(email, senha)
            session["token"] = dados["token"]
            session["aluno_id"] = dados["record"]["id"]
            session["aluno_nome"] = dados["record"].get("name", email)
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
        turmas = pb.listar_turmas()
        atividades_por_turma = {
            t["id"]: pb.listar_atividades_por_turma(t["id"]) for t in turmas
        }
        aluno_nome = session.get("aluno_nome", "")
        return render_template(
            "index.html",
            turmas=turmas,
            atividades_por_turma=atividades_por_turma,
            aluno_nome=aluno_nome,
        )

    # ------------------------------------------------------------------
    # Motor de atividades

    @app.route("/atividade/<ativ_id>")
    @requer_login
    def atividade(ativ_id: str):
        ativ = pb.buscar_atividade(ativ_id)

        disponivel, motivo = _atividade_disponivel(ativ)
        if not disponivel:
            return render_template("auth/atividade_indisponivel.html", atividade=ativ, motivo=motivo)

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
        aluno_nome = session.get("aluno_nome", "")
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
        questao = pb.buscar_questao(questao_id)
        total = session.get("total", 0)
        num = total - len(session.get("fila", []))
        return _render_questao(questao, num, total, session.get("ativ_id", ""))

    @app.route("/htmx/responder", methods=["POST"])
    @requer_login
    def htmx_responder():
        tipo = request.form.get("tipo", "")
        questao_id = request.form.get("questao_id", "")
        ativ_id = session.get("ativ_id", "")

        if tipo not in ("mc4", "mc5", "vf", "associativa"):
            return "", 400

        questao = pb.buscar_questao(questao_id)

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
        else:
            respostas = {
                k.removeprefix("par_"): v
                for k, v in request.form.items()
                if k.startswith("par_")
            }
            resultado = validar_associativa(questao, respostas)
            resposta_raw = str(respostas)

        respostas_sessao = session.get("respostas", [])
        respostas_sessao.append(resultado)
        session["respostas"] = respostas_sessao
        session.modified = True

        try:
            pb.registrar_tentativa({
                "questao": questao_id,
                "tipo_questao": tipo,
                "resposta_dada": str(resposta_raw),
                "correta": resultado["correta"],
                "score_raw": resultado["score_raw"],
                "score_max": resultado["score_max"],
                "duracao_seg": 0,
                "aluno_id": session.get("aluno_id", ""),
                "aluno_nome": session.get("aluno_nome", ""),
            })
        except Exception as exc:
            log.warning("registrar_tentativa falhou: %s", exc)

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
            return render_template(
                "components/_placar.html",
                score_raw=score_raw,
                score_max=score_max,
                ativ_id=ativ_id,
            )

        proxima_id = fila.pop(0)
        session["fila"] = fila
        session.modified = True

        num = total - len(fila)
        questao = pb.buscar_questao(proxima_id)
        return _render_questao(questao, num, total, ativ_id)

    @app.route("/htmx/resultado/<ativ_id>")
    @requer_login
    def htmx_resultado(ativ_id: str):
        respostas = session.get("respostas", [])
        score_raw = sum(r.get("score_raw", 0) for r in respostas)
        score_max = sum(r.get("score_max", 0) for r in respostas)
        return render_template(
            "components/_placar.html",
            score_raw=score_raw,
            score_max=score_max,
            ativ_id=ativ_id,
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
