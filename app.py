import os
from flask import Flask, render_template, request, session, redirect, url_for
from pb import PocketBaseClient
from questao import validar_mc, validar_vf, validar_associativa


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

    pb_url = os.environ.get("PB_URL", "http://127.0.0.1:8090")
    if config:
        app.config.update(config)
        pb_url = config.get("PB_URL", pb_url)

    pb = PocketBaseClient(pb_url)
    app.extensions["pb"] = pb

    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.route("/")
    def index():
        turmas = pb.listar_turmas()
        return render_template("index.html", turmas=turmas)

    @app.route("/atividade/<ativ_id>")
    def atividade(ativ_id: str):
        ativ = pb.buscar_atividade(ativ_id)
        questoes = ativ.get("questoes", [])
        session["fila"] = questoes
        session["ativ_id"] = ativ_id
        session["respostas"] = []
        primeira = questoes[0] if questoes else None
        return render_template("quiz/shell.html", atividade=ativ, primeira_questao=primeira)

    @app.route("/htmx/questao/<questao_id>")
    def htmx_questao(questao_id: str):
        questao = pb.buscar_questao(questao_id)
        template_map = {
            "mc4": "components/_questao_mc.html",
            "mc5": "components/_questao_mc.html",
            "vf": "components/_questao_vf.html",
            "associativa": "components/_questao_assoc.html",
        }
        template = template_map.get(questao["tipo"], "components/_questao_mc.html")
        return render_template(template, questao=questao)

    @app.route("/htmx/responder", methods=["POST"])
    def htmx_responder():
        tipo = request.form.get("tipo", "")
        questao_id = request.form.get("questao_id", "")

        if tipo not in ("mc4", "mc5", "vf", "associativa"):
            return "", 400

        questao = pb.buscar_questao(questao_id)

        if tipo in ("mc4", "mc5"):
            resposta = request.form.get("resposta", "")
            resultado = validar_mc(questao, resposta)
        elif tipo == "vf":
            respostas = {k.removeprefix("vf_"): v == "true" for k, v in request.form.items() if k.startswith("vf_")}
            resultado = validar_vf(questao, respostas)
        elif tipo == "associativa":
            respostas = {k.removeprefix("par_"): v for k, v in request.form.items() if k.startswith("par_")}
            resultado = validar_associativa(questao, respostas)
        else:
            return "", 400

        return render_template("components/_feedback.html", resultado=resultado, questao=questao)

    @app.route("/htmx/proxima/<ativ_id>")
    def htmx_proxima(ativ_id: str):
        fila: list = session.get("fila", [])
        if not fila:
            return redirect(url_for("htmx_resultado", ativ_id=ativ_id))
        proxima_id = fila.pop(0)
        session["fila"] = fila
        questao = pb.buscar_questao(proxima_id)
        template_map = {
            "mc4": "components/_questao_mc.html",
            "mc5": "components/_questao_mc.html",
            "vf": "components/_questao_vf.html",
            "associativa": "components/_questao_assoc.html",
        }
        template = template_map.get(questao["tipo"], "components/_questao_mc.html")
        return render_template(template, questao=questao)

    @app.route("/htmx/resultado/<ativ_id>")
    def htmx_resultado(ativ_id: str):
        respostas = session.get("respostas", [])
        score_raw = sum(r.get("score_raw", 0) for r in respostas)
        score_max = sum(r.get("score_max", 0) for r in respostas)
        return render_template("components/_placar.html", score_raw=score_raw, score_max=score_max)

    @app.route("/relatorio/turma/<turma_id>")
    def relatorio_turma(turma_id: str):
        return render_template("relatorio/turma.html", turma_id=turma_id)

    @app.route("/relatorio/aluno/<aluno_id>")
    def relatorio_aluno(aluno_id: str):
        return render_template("relatorio/aluno.html", aluno_id=aluno_id)

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=8091)
