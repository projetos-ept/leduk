# LeDuk — Lições aprendidas (convenções permanentes)

Este arquivo registra bugs recorrentes já resolvidos e as convenções que
evitam sua reintrodução. Qualquer agente escrevendo um novo
`scripts/migrate_*.py` ou método em `pb.py` deve consultar isto antes.

---

## 1. Campos `bool` nunca devem ser `"required": True`

**Sintoma:** PocketBase rejeita a inserção com `validation_required` mesmo
quando o campo bool foi enviado explicitamente como `false`.

**Causa:** o PocketBase trata `false` como "valor vazio" em campos bool
obrigatórios — o validador de required não distingue "ausente" de "falso".

**Regra:** todo campo `{"type": "bool", ...}` em qualquer schema criado por
`scripts/migrate_*.py` (ou em qualquer payload montado por `pb.py`) deve usar

```python
{"name": "ativo", "type": "bool", "required": False}
```

Nunca `"required": True` em campo bool — mesmo que a lógica de negócio exija
que ele sempre tenha um valor. Trate a obrigatoriedade na camada de aplicação
(Flask), não no schema do PocketBase.

**Auditoria (2026-07):** verificado todos os `scripts/migrate_*.py` e `pb.py`
existentes — nenhuma ocorrência de `bool` com `required: True`. Nenhum script
cria ou altera o schema de `alternativas` (`jf69g6b4qr80hq3`) ou `itens_vf`
(`dkc5b8csbsus7es`); essas collections foram seedadas fora deste conjunto de
scripts. Se um script futuro precisar tocar essas collections, aplicar a
mesma regra aos campos `correta`/`gabarito`.

---

## 2. Regras de acesso vão no payload de criação, nunca em PATCH posterior

**Sintoma:** collection criada por migração fica admin-only até alguém
liberar manualmente pelo painel do PocketBase.

**Causa:** o PocketBase cria collections com `listRule`/`viewRule`/etc. como
`null` (admin-only) por padrão, se o payload de criação não especificar.

**Regra:** todo `POST /api/collections` deve incluir as regras no mesmo
payload:

```python
"listRule": "", "viewRule": "",
"createRule": '@request.auth.id != ""',
"updateRule": '@request.auth.id != ""',
"deleteRule": '@request.auth.id != ""',
```

Exceções documentadas (regras próprias, não seguem o padrão acima):
`tentativas` (escrita pública, para o aluno enviar respostas sem custom auth
adicional) e `tokens_senha` (`createRule`/`updateRule` públicos, necessários
para o fluxo de redefinição de senha sem login).

Ver `README.md` → "Regras de acesso (listRule / viewRule)" para a tabela
completa por collection.

---

## 3. Ordem de criação das collections

O PocketBase rejeita campos `relation` apontando para collections que ainda
não existem. Toda migração que cria uma collection com relation deve
resolver o ID da collection-alvo **em runtime** (via `GET /api/collections/<nome>`)
em vez de hardcodar — e a documentação da ordem de dependências fica em
`README.md` → "Ordem de criação obrigatória".

---

## 4. Migrações devem ser idempotentes

Todo `scripts/migrate_*.py` verifica se a collection/campo já existe antes de
criar (`get_collection(token, nome)` retornando `None` em 404) e imprime
`[OK] ... já existe` em vez de falhar. Isso permite rodar o mesmo script
várias vezes em produção sem efeito colateral.

---

## 5. Criação em várias etapas precisa de rollback se uma etapa falhar

**Sintoma real (2026-07):** importação de questões via JSON criava o registro
da questão (`questoes`) e, em seguida, os subitens (`alternativas`/`itens_vf`/
`pares_associativos`) em chamadas HTTP separadas. Quando a criação de um
subitem falhava (rede, validação, ou **permissão negada** — ver lição 6), a
questão-pai já gravada ficava **órfã**: só o enunciado aparecia no banco, sem
nenhuma alternativa, mesmo o JSON de origem estando correto. Reimportar o
mesmo arquivo então empilhava mais cópias parciais.

**Regra:** ao criar um registro que depende de subitens criados em chamadas
subsequentes, envolva a criação dos subitens em `try/except` e, se falhar,
**apague o registro-pai** (`excluir_questao`, etc.) antes de reportar o erro —
nunca deixe um registro "enunciado-only" para trás. Ver `_importar_questoes`
em `app.py` para o padrão de referência.

**Limpeza de dados já afetados:** `scripts/cleanup_questoes_duplicadas.py`
localiza grupos de questões com o mesmo (disciplina, tipo, enunciado
normalizado), mantém a mais completa (mais subitens) e remove as demais —
rode em dry-run primeiro (padrão), depois com `--apply`.

---

## 6. `data=` em multipart não serializa bool — vira string capitalizada

**Sintoma real (2026-07):** alternativas com imagem e `correta=False` eram
rejeitadas ou gravadas incorretamente pelo PocketBase.

**Causa:** `requests.post(..., data={"correta": False}, files=...)` (usado
para multipart, quando há upload de imagem) não tem tipo booleano nativo —
`requests` faz `str(False)` internamente, enviando o campo como a string
**`"False"`** (Python, capitalizado). O parser de bool do PocketBase espera
`"true"`/`"false"` (minúsculo) e pode rejeitar ou interpretar mal a forma
capitalizada. Isso só afeta o caminho multipart (upload de imagem); o caminho
JSON puro (`_post`/`_patch`, sem imagem) sempre serializou bool corretamente.

**Regra:** `PocketBaseClient._post_multipart`/`_patch_multipart` normalizam
automaticamente qualquer valor `True`/`False` em `data` para as strings
`"true"`/`"false"` antes de enviar (ver `_normalizar_bool_multipart` em
`pb.py`). Qualquer novo método que use multipart deve passar por esses
wrappers — não chamar `requests.post(..., data=...)` diretamente.

---

## 7. Importação em massa deve checar duplicatas — contra o banco e dentro do próprio lote

**Sintoma real (2026-07):** reimportar o mesmo JSON (às vezes sem querer, por
causa da lição 5) criava questões repetidas no banco, sem aviso.

**Regra:** antes de criar cada registro num fluxo de importação em massa,
comparar contra uma chave de deduplicação (ex: `(tipo, enunciado normalizado)`
via `_chave_duplicata` em `app.py`) tanto contra o que **já existe no banco**
quanto contra o que **já foi processado no mesmo lote**. Reportar duplicatas
separadamente de erros de validação (são esperadas, não são um bug) e deixar
claro na pré-visualização (dry-run) quantas serão puladas antes de confirmar.

---

## 8. Apagar um registro-pai exige apagar os filhos primeiro (sem cascadeDelete)

**Sintoma real (2026-07):** após a correção da lição 5, algumas questões
criadas *antes* da correção (com alternativas já existentes, não órfãs)
falhavam ao excluir — tanto na rota individual (`500`, exceção não tratada)
quanto na exclusão em massa (falha silenciosa, contabilizada como sucesso
sem realmente remover o registro).

**Causa:** `excluir_questao` apagava só o registro de `questoes`, sem antes
apagar `alternativas`/`itens_vf`/`pares_associativos` que ainda apontam para
ela via relation obrigatória. O PocketBase recusa (`400 Bad Request`,
"Failed to delete record...") apagar um registro enquanto outro ainda o
referencia por uma relation obrigatória sem `cascadeDelete` habilitado nela —
e essas collections de subitem foram seedadas fora dos scripts deste repo,
então não há garantia de que `cascadeDelete` esteja ligado.

**Regra:** antes de `excluir_questao(id)`, sempre chamar
`pb.apagar_subitens_questao(id)` — que verifica as três collections de
subitem (não só a do `tipo` declarado, para tolerar dados legados/
reclassificados de forma inconsistente) e apaga tudo que referencia a
questão. O mesmo padrão vale para qualquer registro-pai com filhos via
relation obrigatória: **filhos primeiro, pai depois** — nunca assuma que
`cascadeDelete` está configurado na collection filha.

**Resiliência da rota:** mesmo com o cascade correto, uma falha de exclusão
ainda pode ocorrer (rede, outra relation não prevista). A rota de exclusão
individual e a de exclusão em massa **nunca devem deixar uma exceção não
tratada propagar** (isso derruba a requisição com 500) — capturar, logar, e
redirecionar com uma mensagem legível (`_erro_http`) em vez de crashar.

---

## 9. Importação de JSON deve tolerar campos ausentes/renomeados de geradores externos

**Sintoma real (2026-07):** JSON de questões gerado por uma ferramenta externa
(NotebookLM) tinha `alternativas` sem o campo `letra` (só `texto`/`correta`) e
`itens_vf` usando `texto` em vez de `afirmacao` — o PocketBase rejeitava a
criação por campo obrigatório ausente, e a importação falhava questão por
questão mesmo com os dados essenciais presentes.

**Regra:** campos que são deriváveis pela posição no array (`letra` em
alternativas: A, B, C...; `ordem` em itens_vf) devem ser **gerados
automaticamente quando ausentes**, nunca exigidos do JSON de entrada. Campos
com nomes alternativos plausíveis vindos de geradores externos (`texto` para
`afirmacao`) devem ser aceitos como alias. Essa normalização (`_normalizar_alternativas`,
`_normalizar_itens_vf` em `app.py`) deve rodar **antes** de qualquer validação
e criação, e idêntica tanto no dry-run (`_analisar_questoes`) quanto na
importação real (`_importar_questoes`), para a pré-visualização não mentir
sobre o que vai ser gravado. As funções sempre copiam o dict antes de alterar
(nunca mutam a lista original) e só preenchem o que está ausente — um `letra`
ou `ordem` já explícito no JSON nunca é sobrescrito.

**Cuidado com a direção do alias:** ao aceitar um nome alternativo (ex:
`gabarito` como alias de `correta`), a normalização deve sempre convergir
**para o nome real do campo no PocketBase** (`correta`, conforme
`pb.criar_item_vf`) — nunca o inverso. Renomear o campo correto para o alias
por engano reintroduziria o mesmo erro de "campo obrigatório ausente" que a
normalização deveria resolver.

---

## 10. Campos usados em fluxos anônimos/opcionais nunca devem ser `required: True`

**Sintoma real (2026-07):** o modo público (visitante responde uma atividade
sem criar conta) gravava tentativas com `aluno_id=""` para identificar o
respondente por email em vez de conta. Se `aluno_id` estivesse `required:
True` no schema de `tentativas`, o PocketBase rejeitava **toda** tentativa
pública com `validation_required` — nada era gravado, e a falha era
silenciosa do ponto de vista do visitante (a rota não crasha, só não
persiste nada).

**Causa:** esta é a mesma classe de bug da lição 1 (bool `required: True`
rejeita `false` por tratá-lo como "vazio"), mas generalizada: qualquer campo
que o fluxo de aplicação legitimamente preenche com um "valor vazio"
(`""`, `False`, `None`/relation não selecionada) para representar "não se
aplica aqui" quebra se o schema exigir presença.

**Regra:** ao desenhar um campo que serve tanto o fluxo autenticado quanto
um fluxo anônimo/opcional (relation para o usuário, bool de flag, texto de
identificação alternativa), o campo é **sempre** `required: False` no
schema do PocketBase — a obrigatoriedade condicional (“obrigatório só para
alunos com conta”) fica na camada de aplicação (Flask), nunca no PocketBase.
Isso estende a lição 1 (que cobria só `bool`) para **qualquer tipo de
campo** — `relation`, `text`, `number` — sempre que o campo puder ser
legitimamente vazio em algum fluxo suportado.

**Correção aplicada:** `scripts/migrate_tentativas_questao_optional.py`
agora torna `questao` **e** `aluno_id` opcionais na mesma migração (script
idempotente, roda em qualquer instalação nova ou já existente).
`scripts/verificar_modo_publico.py` inclui uma checagem dedicada
(`checar_aluno_id_opcional`) que detecta e corrige (`--fix`) o campo antes
mesmo de tentar o POST anônimo de teste.

---

## 11. Cascade de exclusão precisa cobrir *todas* as gerações de schema de um recurso, não só a atual

**Sintoma real (2026-07, produção):** `excluir_turma` já fazia cascade de
matrículas, `turma_disciplina`, formulários de cadastro, `turma_materiais` e
boletins (lições 8 e correções anteriores), mas a exclusão de turma ainda
falhava com `400 Bad Request` no `DELETE .../turmas/records/<id>` — sem
nenhuma mensagem de qual coleção bloqueava, porque cada etapa do cascade
engolia a exceção com `except: pass`, sem logar nada.

**Causa:** a collection `materiais` tem **dois modelos de dados coexistindo**
(ver `pb.listar_materiais`): o pivô novo `turma_materiais` (many-to-many,
compartilhável entre turmas) e um campo legado `materiais.turma` **direto e
`required: True`** (`scripts/migrate_materiais.py`), usado como fallback para
registros criados antes do modelo de pivô existir. O cascade cobria o pivô
mas nunca tocava o campo legado — qualquer turma com materiais antigos
(pré-pivô) ficava com um `materiais` ainda apontando para ela via relation
obrigatória, e o PocketBase recusa o `DELETE` da turma nessa condição (mesma
mecânica da lição 8, agora numa collection diferente).

**Regra:** ao adicionar um recurso vinculado a uma entidade, verificar se
existe mais de uma "geração" de schema para esse vínculo (pivô novo +
campo direto legado, por exemplo) e cobrir **todas** no cascade de exclusão
— não só o modelo atualmente usado pela maioria dos registros. Como
`materiais.turma` é `required: True`, não pode ser anulado por `PATCH`
(lição 10 se aplica ao inverso: campo obrigatório não aceita `null`); o
registro-filho precisa ser removido (e qualquer pivô que aponte para ele,
para não deixar `turma_materiais` órfão) antes do `DELETE` do pai.

**Regra de diagnosticabilidade:** todo `except Exception: pass` dentro de um
cascade de exclusão deve virar `except Exception as exc: log.warning(...)`
com o nome da collection/registro envolvido. Um cascade "silencioso" transforma
qualquer vínculo não previsto em um `400` opaco no passo final, sem pista de
qual coleção causou — o log é o que permite diagnosticar em produção sem
precisar reproduzir localmente.
