"""Cliente HTTP mínimo para a API do PocketBase."""
import requests

# Campos gerados pelo PocketBase que não devem ser reenviados ao clonar registros.
_CAMPOS_PB = {"id", "created", "updated", "collectionId", "collectionName", "expand"}


class PocketBaseClient:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = self.token
        return h

    def _auth_headers(self) -> dict:
        """Headers sem Content-Type para requisições multipart."""
        h = {}
        if self.token:
            h["Authorization"] = self.token
        return h

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = requests.get(f"{self.base_url}{path}", headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict) -> dict:
        resp = requests.post(f"{self.base_url}{path}", headers=self._headers(), json=data)
        resp.raise_for_status()
        return resp.json()

    def _post_multipart(self, path: str, data: dict, files: dict | None = None) -> dict:
        resp = requests.post(f"{self.base_url}{path}", headers=self._auth_headers(),
                             data=data, files=files or {})
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, data: dict) -> dict:
        resp = requests.patch(f"{self.base_url}{path}", headers=self._headers(), json=data)
        resp.raise_for_status()
        return resp.json()

    def _patch_multipart(self, path: str, data: dict, files: dict | None = None) -> dict:
        resp = requests.patch(f"{self.base_url}{path}", headers=self._auth_headers(),
                              data=data, files=files or {})
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> None:
        resp = requests.delete(f"{self.base_url}{path}", headers=self._auth_headers())
        resp.raise_for_status()

    # --- Collections ---

    def buscar_questao(self, questao_id: str) -> dict:
        questao = self._get(f"/api/collections/questoes/records/{questao_id}")
        tipo = questao.get("tipo", "")
        if tipo in ("mc4", "mc5"):
            result = self._get(
                "/api/collections/alternativas/records",
                params={"filter": f'questao="{questao_id}"', "sort": "letra"},
            )
            questao["alternativas"] = result.get("items", [])
        elif tipo == "vf":
            result = self._get(
                "/api/collections/itens_vf/records",
                params={"filter": f'questao="{questao_id}"', "sort": "ordem"},
            )
            questao["itens_vf"] = result.get("items", [])
        elif tipo == "associativa":
            result = self._get(
                "/api/collections/pares_associativos/records",
                params={"filter": f'questao="{questao_id}"', "sort": "ordem"},
            )
            questao["pares_associativos"] = result.get("items", [])
        return questao

    def buscar_atividade(self, ativ_id: str) -> dict:
        return self._get(f"/api/collections/atividades/records/{ativ_id}")

    def buscar_turma(self, turma_id: str) -> dict:
        return self._get(f"/api/collections/turmas/records/{turma_id}")

    def buscar_disciplina(self, disciplina_id: str) -> dict:
        return self._get(f"/api/collections/disciplinas/records/{disciplina_id}")

    def listar_turmas(self) -> list:
        result = self._get("/api/collections/turmas/records", params={"sort": "nome"})
        return result.get("items", [])

    def listar_atividades_por_disciplina(self, turma_id: str, disciplina_id: str) -> list:
        result = self._get(
            "/api/collections/atividades/records",
            params={
                "filter": f'turma="{turma_id}"&&disciplina="{disciplina_id}"&&ativa=true',
                "sort": "titulo",
            },
        )
        return result.get("items", [])

    def listar_materiais(self, turma_id: str, disciplina_id: str) -> list:
        result = self._get(
            "/api/collections/materiais/records",
            params={
                "filter": f'turma="{turma_id}"&&disciplina="{disciplina_id}"&&ativo=true',
                "sort": "ordem",
            },
        )
        return result.get("items", [])

    def listar_disciplinas_da_turma(self, turma_id: str) -> list:
        """Derives unique disciplines for a turma from expanded active activities."""
        atividades = self.listar_atividades_por_turma(turma_id)
        seen: dict[str, dict] = {}
        for a in atividades:
            disc = (a.get("expand") or {}).get("disciplina")
            if disc and disc["id"] not in seen:
                seen[disc["id"]] = disc
        return list(seen.values())

    def listar_atividades_por_turma(self, turma_id: str) -> list:
        result = self._get(
            "/api/collections/atividades/records",
            params={
                "filter": f'turma="{turma_id}"&&ativa=true',
                "expand": "disciplina",
                "sort": "titulo",
            },
        )
        return result.get("items", [])

    def login_aluno(self, email: str, senha: str) -> dict:
        """POST /api/collections/users/auth-with-password → {token, record}."""
        return self._post(
            "/api/collections/users/auth-with-password",
            {"identity": email, "password": senha},
        )

    def get_aluno(self, token: str) -> dict:
        """GET /api/collections/users/records/me com token do aluno."""
        resp = requests.get(
            f"{self.base_url}/api/collections/users/records/me",
            headers={"Authorization": token, "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()

    def registrar_tentativa(self, dados: dict) -> dict:
        return self._post("/api/collections/tentativas/records", dados)

    def criar_tentativa(self, ativ_id: str, aluno_id: str, aluno_nome: str, numero: int) -> dict:
        return self._post("/api/collections/tentativas/records", {
            "atividade": ativ_id,
            "aluno_id": aluno_id,
            "aluno_nome": aluno_nome,
            "numero_tentativa": numero,
            "concluida": False,
            "nota_liberada": False,
            "questoes_respondidas": 0,
        })

    def atualizar_progresso(self, tentativa_id: str, respondidas: int) -> dict:
        return self._patch(f"/api/collections/tentativas/records/{tentativa_id}", {
            "questoes_respondidas": respondidas,
        })

    def progresso_tentativa_atual(self, ativ_id: str, aluno_id: str) -> dict | None:
        result = self._get(
            "/api/collections/tentativas/records",
            params={
                "filter": f'atividade="{ativ_id}"&&aluno_id="{aluno_id}"&&concluida=false',
                "sort": "-created",
            },
        )
        items = result.get("items", [])
        return items[0] if items else None

    def listar_tentativas_aluno(self, ativ_id: str, aluno_id: str) -> list:
        result = self._get(
            "/api/collections/tentativas/records",
            params={
                "filter": f'atividade="{ativ_id}"&&aluno_id="{aluno_id}"&&concluida=true',
                "sort": "-created",
            },
        )
        return result.get("items", [])

    def status_atividade_aluno(self, ativ_id: str, aluno_id: str, max_tentativas: int = 0) -> dict:
        tentativas = self.listar_tentativas_aluno(ativ_id, aluno_id)
        usadas = len(tentativas)
        melhor = max((t.get("score_percentual", 0) for t in tentativas), default=0)
        liberada = any(t.get("nota_liberada", False) for t in tentativas)
        melhor_tent = max(tentativas, key=lambda t: t.get("score_percentual", 0), default=None)
        return {
            "tentativas_usadas": usadas,
            "max_tentativas": max_tentativas,
            "pode_tentar": max_tentativas == 0 or usadas < max_tentativas,
            "melhor_nota": melhor,
            "nota_liberada": liberada,
            "ultima_tentativa": tentativas[0] if tentativas else None,
            "melhor_tentativa_id": melhor_tent["id"] if melhor_tent else None,
            "melhor_nota_final": melhor_tent.get("nota_final") if melhor_tent else None,
        }

    def buscar_tentativa(self, tentativa_id: str) -> dict:
        return self._get(f"/api/collections/tentativas/records/{tentativa_id}")

    def listar_historico_aluno(self, aluno_id: str) -> list:
        result = self._get(
            "/api/collections/tentativas/records",
            params={
                "filter": f'aluno_id="{aluno_id}"&&concluida=true',
                "sort": "-created",
            },
        )
        return result.get("items", [])

    def listar_respostas_tentativa(self, tentativa_id: str) -> list:
        result = self._get(
            "/api/collections/tentativas/records",
            params={
                "filter": f'tentativa_id="{tentativa_id}"',
                "sort": "created",
            },
        )
        return result.get("items", [])

    def buscar_atividade_expandido(self, ativ_id: str) -> dict:
        return self._get(
            f"/api/collections/atividades/records/{ativ_id}",
            params={"expand": "disciplina"},
        )

    def contar_novas_atividades(self, turma_id: str, disciplina_id: str, desde: str) -> int:
        result = self._get(
            "/api/collections/atividades/records",
            params={
                "filter": f'turma="{turma_id}"&&disciplina="{disciplina_id}"&&ativa=true&&created>"{desde}"',
            },
        )
        return len(result.get("items", []))

    def concluir_tentativa(self, tentativa_id: str, score_raw: int, score_max: int, nota_automatica: bool) -> dict:
        pct = round(score_raw / score_max * 100) if score_max > 0 else 0
        return self._patch(f"/api/collections/tentativas/records/{tentativa_id}", {
            "concluida": True,
            "score_raw": score_raw,
            "score_max": score_max,
            "score_percentual": pct,
            "nota_liberada": nota_automatica,
        })

    def liberar_nota(self, tentativa_id: str) -> dict:
        return self._patch(f"/api/collections/tentativas/records/{tentativa_id}", {
            "nota_liberada": True,
        })

    def patch_tentativa_nota_final(self, tentativa_id: str, nota_final: float) -> dict:
        return self._patch(f"/api/collections/tentativas/records/{tentativa_id}", {
            "nota_final": nota_final,
        })

    def listar_tentativas_para_avaliar(self, ativ_id: str) -> list:
        result = self._get(
            "/api/collections/tentativas/records",
            params={
                "filter": f'atividade="{ativ_id}"&&concluida=true&&nota_liberada=false',
                "sort": "-created",
            },
        )
        return result.get("items", [])

    def avaliar_questao_aberta(self, record_id: str, score_raw: float, score_max: float, comentario: str = "") -> dict:
        data: dict = {"score_raw": score_raw, "score_max": score_max}
        if comentario:
            data["comentario_professor"] = comentario
        return self._patch(f"/api/collections/tentativas/records/{record_id}", data)

    def tentativas_por_atividade(self, ativ_id: str, aluno_id: str) -> list:
        result = self._get(
            "/api/collections/tentativas/records",
            params={"filter": f'aluno_id="{aluno_id}"&&atividade="{ativ_id}"'},
        )
        return result.get("items", [])

    def listar_todas_atividades_turma(self, turma_id: str) -> list:
        result = self._get(
            "/api/collections/atividades/records",
            params={"filter": f'turma="{turma_id}"', "expand": "disciplina", "sort": "titulo"},
        )
        return result.get("items", [])

    def listar_tentativas_atividade(self, ativ_id: str) -> list:
        result = self._get(
            "/api/collections/tentativas/records",
            params={"filter": f'atividade="{ativ_id}"&&concluida=true', "sort": "-score_percentual"},
        )
        return result.get("items", [])

    def criar_atividade(self, data: dict) -> dict:
        return self._post("/api/collections/atividades/records", data)

    def atualizar_atividade(self, ativ_id: str, data: dict) -> dict:
        return self._patch(f"/api/collections/atividades/records/{ativ_id}", data)

    def excluir_atividade(self, ativ_id: str) -> None:
        self._delete(f"/api/collections/atividades/records/{ativ_id}")

    def listar_disciplinas(self) -> list:
        result = self._get("/api/collections/disciplinas/records", params={"sort": "nome"})
        return result.get("items", [])

    # --- Questões ---

    def listar_questoes_atividade(self, questao_ids: list) -> list:
        result = []
        for qid in questao_ids:
            try:
                result.append(self.buscar_questao(qid))
            except Exception:
                pass
        return result

    def listar_questoes_disciplina(self, disciplina_id: str, filtros: dict | None = None) -> list:
        """Lista todas as questões do banco de uma disciplina, com filtros opcionais.

        filtros aceita as chaves 'tipo', 'assunto' e 'dificuldade' (valores vazios
        são ignorados). Retorna os registros crus (sem expandir subitens).
        """
        filtro = f'disciplina="{disciplina_id}"'
        for campo in ("tipo", "assunto", "dificuldade"):
            val = (filtros or {}).get(campo)
            if val:
                filtro += f'&&{campo}="{val}"'
        result = self._get(
            "/api/collections/questoes/records",
            params={"filter": filtro, "sort": "-created", "perPage": 200},
        )
        return result.get("items", [])

    def clonar_questao(self, questao_id: str) -> dict:
        """Duplica uma questão (e seus subitens) como um novo registro independente."""
        orig = self.buscar_questao(questao_id)
        ignorar = _CAMPOS_PB | {"alternativas", "itens_vf", "pares_associativos", "imagem"}
        data = {k: v for k, v in orig.items() if k not in ignorar}
        data["enunciado"] = f'{orig.get("enunciado", "")} (cópia)'
        nova = self.criar_questao(data)
        novo_id = nova["id"]
        tipo = orig.get("tipo", "")
        if tipo in ("mc4", "mc5"):
            for a in orig.get("alternativas", []):
                self.criar_alternativa({
                    "questao": novo_id,
                    "letra": a.get("letra", ""),
                    "texto": a.get("texto", ""),
                    "correta": a.get("correta", False),
                    "feedback": a.get("feedback", ""),
                })
        elif tipo == "vf":
            for it in orig.get("itens_vf", []):
                self.criar_item_vf({
                    "questao": novo_id,
                    "afirmacao": it.get("afirmacao", ""),
                    "correta": it.get("correta", False),
                    "ordem": it.get("ordem", 0),
                })
        elif tipo == "associativa":
            for p in orig.get("pares_associativos", []):
                self.criar_par_associativo({
                    "questao": novo_id,
                    "coluna_a": p.get("coluna_a", ""),
                    "coluna_b": p.get("coluna_b", ""),
                    "ordem": p.get("ordem", 0),
                })
        return nova

    def reclassificar_questao(self, questao_id: str, nova_disciplina_id: str = "",
                              novo_assunto: str | None = None) -> dict:
        """Move a questão para outra disciplina e/ou muda seu assunto."""
        data: dict = {}
        if nova_disciplina_id:
            data["disciplina"] = nova_disciplina_id
        if novo_assunto is not None:
            data["assunto"] = novo_assunto
        return self._patch(f"/api/collections/questoes/records/{questao_id}", data)

    def contar_uso_questao(self, questao_id: str) -> int:
        """Conta em quantas atividades essa questão aparece (atividades.questoes[])."""
        result = self._get(
            "/api/collections/atividades/records",
            params={"filter": f'questoes~"{questao_id}"', "perPage": 1},
        )
        return result.get("totalItems", 0)

    def criar_questao(self, data: dict, imagem=None) -> dict:
        if imagem:
            return self._post_multipart("/api/collections/questoes/records", data, {"imagem": imagem})
        return self._post("/api/collections/questoes/records", data)

    def atualizar_questao(self, questao_id: str, data: dict, imagem=None) -> dict:
        if imagem:
            return self._patch_multipart(f"/api/collections/questoes/records/{questao_id}",
                                         data, {"imagem": imagem})
        return self._patch(f"/api/collections/questoes/records/{questao_id}", data)

    def excluir_questao(self, questao_id: str) -> None:
        self._delete(f"/api/collections/questoes/records/{questao_id}")

    # --- Alternativas ---

    def criar_alternativa(self, data: dict, imagem=None) -> dict:
        if imagem:
            return self._post_multipart("/api/collections/alternativas/records", data, {"imagem": imagem})
        return self._post("/api/collections/alternativas/records", data)

    def excluir_alternativa(self, alt_id: str) -> None:
        self._delete(f"/api/collections/alternativas/records/{alt_id}")

    # --- Itens V/F ---

    def criar_item_vf(self, data: dict) -> dict:
        return self._post("/api/collections/itens_vf/records", data)

    def excluir_item_vf(self, item_id: str) -> None:
        self._delete(f"/api/collections/itens_vf/records/{item_id}")

    # --- Pares associativos ---

    def criar_par_associativo(self, data: dict) -> dict:
        return self._post("/api/collections/pares_associativos/records", data)

    def excluir_par_associativo(self, par_id: str) -> None:
        self._delete(f"/api/collections/pares_associativos/records/{par_id}")
