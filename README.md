# AtribuiçãoProfessor

Automação (Python + Playwright) que atribui **turmas e matérias** ao perfil de cada professor no
**CENSO** do portal Pegasus (`apps.uno-internacional.com`).

Para cada professor da planilha, o fluxo **lê o estado atual** do perfil no CENSO e escreve **apenas
o que estiver faltando** (delta), de forma idempotente:

- **Turmas:** vêm da planilha (`login` + `turma` + `periodo`), combinadas com o conjunto fixo de anos
  `ANOS_FIXOS` definido no código.
- **Matérias:** vêm de uma **lista fixa** (`MATERIAS_PADRAO`) ou da aba opcional `Materias` da
  planilha.

> **Nota sobre o Gestor de Classes (GC):** o módulo `harvester.py` lê o GC e é uma ferramenta **ativa
> de inspeção/auditoria**, mas na v1 ele **não** alimenta o fluxo principal — as matérias são a lista
> fixa acima. O porquê dessa escolha está na [ADR-006](docs/adr/ADR-006-curriculo-fixo-em-codigo.md).

A cada execução, tudo o que foi feito é registrado em um log xlsx (uma linha por operação) — essa é a
**fonte de verdade**, já que o portal não emite confirmação confiável ao salvar.

---

## Pré-requisitos

- **Windows** com **PowerShell** (os comandos abaixo usam `.venv\Scripts\...`).
- **Python 3.10+** (o código usa anotações de tipo `list[...] | None`).
- **Google Chrome** instalado (a automação se anexa ao seu Chrome — ver abaixo).
- Acesso ao portal Pegasus com permissão para editar perfis no CENSO.

## 1. Clonar e instalar

```powershell
git clone <URL-do-repositorio> AutoProfProfile
cd AutoProfProfile

python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

> **Sobre `playwright install`:** no modo `manual` (padrão) o script **anexa-se ao seu Chrome** via
> CDP — o navegador embutido do Playwright **não** é usado, então `playwright install chromium` é
> opcional. Só seria necessário para o futuro modo `auto`.

## 2. Configurar (`.env`)

Copie `.env.example` para `.env` e ajuste:

| Variável | Descrição |
|---|---|
| `COLEGIO_ID` | id do colégio (ex.: `29457`) |
| `CICLO_ID` | ano letivo corrente — **atualizar anualmente** |
| `NIVEL_ID` | `nivelId` da URL do professor (`33` funciona mesmo quando o portal indica `32`) |
| `URL_PEGASUS` / `URL_BASE` | endpoints do portal (as demais URLs são derivadas destas) |
| `CDP_URL` | endereço da depuração remota do Chrome (`http://localhost:9222`) |
| `AUTH_MODE` | `manual` (padrão) ou `auto` (a implementar) |
| `LOG_LEVEL` | nível de log (`INFO` por padrão) |
| `RETRY_MAX` | tentativas por professor com status `parcial`/`erro` (padrão `3`) |

Todas as variáveis têm default em [`src/config.py`](src/config.py), que é a **fonte única** de
configuração — nenhum outro módulo lê `.env` ou monta URLs à mão.

## 3. Autenticação (`AUTH_MODE`)

- **`manual` (padrão):** você abre o Chrome com depuração remota e faz login **manualmente**; o
  script se anexa à sessão já autenticada via CDP. É a escolha atual — ver
  [ADR-001](docs/adr/ADR-001-autenticacao-cdp-manual.md).
- **`auto` (a implementar):** o script abriria o próprio Chrome e faria o login. Hoje é um stub
  (`NotImplementedError`).

Para o modo manual, abra o Chrome assim **e faça login no Pegasus nessa janela** antes de rodar:

```powershell
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome_pegasus_dev"
```

## 4. Preparar a planilha de entrada

`dados/input_professores.xlsx`, aba **`professores`** — uma linha por professor (linhas com o mesmo
`login` são unidas). Só importam três colunas: `login`, `turma` (letra) e `periodo`.

| login | turma | periodo |
|---|---|---|
| mirela.godoy | G | Matutino |
| joao.silva | A | Vespertino |

A partir de cada linha, o professor recebe uma turma para **cada ano de `ANOS_FIXOS`**
(`1º/5º/6º/7º EF` e `1º/3º EM` na v1). **As colunas de ano (`1° EF`, `9° EF`, …) que possam existir
na planilha são ignoradas** na v1 — ver [ADR-006](docs/adr/ADR-006-curriculo-fixo-em-codigo.md).

**Matérias (opcional):** para sobrescrever a lista fixa, adicione uma aba **`Materias`** com duas
colunas — `nome` da matéria e `série` (ex.: `Matemática` / `7º ano EF AF`). Sem essa aba, vale a
`MATERIAS_PADRAO` de [`src/ingestao.py`](src/ingestao.py).

## 5. Rodar

```powershell
# (recomendado) valide a sessão antes — ver "Validação por partes" abaixo
.venv\Scripts\python -m src.verificar_sessao

# fluxo completo
.venv\Scripts\python -m src.main
```

Ao final, confira o log em `logs/atribuicao_AAAAMMDD_HHMM.xlsx` (ver "Lendo os logs").

Professores que terminam com status `parcial` ou `erro` são automaticamente reprocessados (fila de
retry) até `RETRY_MAX` tentativas — como `processar_professor` relê o estado a cada tentativa, o
delta encolhe e a operação é idempotente
([ADR-007](docs/adr/ADR-007-idempotencia-por-delta.md), [ADR-008](docs/adr/ADR-008-fila-de-retry.md)).

---

## Validação por partes (debug)

Com o Chrome aberto e logado, dá para validar em etapas:

```powershell
# 1) sessão CDP + acesso ao Gestor de Classes (smoke test)
.venv\Scripts\python -m src.verificar_sessao

# 2) inspeção do GC: 5 classes (rápido) e depois completo — confira as contagens contra o portal
#    (ferramenta de auditoria; NÃO faz parte do fluxo do main)
.venv\Scripts\python -m src.harvester 5
.venv\Scripts\python -m src.harvester

# 3) processa UM professor da planilha, ponta a ponta, e exporta o log
.venv\Scripts\python -m src.perfil mirela.godoy

# 4) execução real, limitada aos N primeiros professores
.venv\Scripts\python -m src.main --limite 1
.venv\Scripts\python -m src.main --teste     # atalho: processa só o 1º professor
```

## Lendo os logs

Cada execução gera **um arquivo** `logs/atribuicao_AAAAMMDD_HHMM.xlsx`, com **uma linha por
operação**. Colunas:

| Coluna | Significado |
|---|---|
| `timestamp` | momento da operação (ISO, ex.: `2026-06-25T14:30:45`) |
| `login_professor` | login do professor |
| `persona_id` | id do professor no CENSO (resultado da busca pelo login) |
| `fase` | etapa: `perfil`, `validacao`, `execucao` |
| `acao` | o que aconteceu (ver vocabulário abaixo) |
| `detalhe` | texto livre: turma/matéria afetada ou mensagem de erro (truncada a 300 chars) |
| `status` | situação daquela linha / do professor |

**Vocabulário de `acao`:**

- `turma_adicionada` / `materia_adicionada` — adicionada e confirmada pelo toast "Salvo corretamente!"
- `turma_nao_encontrada` / `materia_nao_encontrada` — opção não localizada no dropdown
- `ja_existia` — nada faltava para o professor
- `turma_faltando` / `materia_faltando` — estava no delta mas não foi confirmada (vira `parcial`)
- `nao_encontrado` — o login não retornou resultado na busca do CENSO
- `erro` / `erro_save_turmas` — exceção, ou o toast de confirmação não apareceu

**Vocabulário de `status`:** `sucesso`, `ja_configurado`, `parcial`, `nao_encontrado`, `erro`.

O console também imprime o progresso (`[tentativa.i/total] login... status`) e um **RESUMO** final
com a contagem por status e a lista de pendentes. A validação é por confirmação de toast, não por
releitura — ver [ADR-009](docs/adr/ADR-009-validacao-por-toast.md).

---

## Desenvolvimento

```powershell
.venv\Scripts\python -m pytest
```

A lógica pura (`matching`, `ingestao`, `registro` e as Fases 1/3 de `perfil`) é coberta por testes
que **não precisam de navegador**. As partes que dependem do portal (inspeção do GC, busca/escrita
no CENSO) são validadas pelos comandos de debug acima, com a sessão logada.

## Estrutura

```
src/
  config.py            # .env + URLs derivadas + constantes (fonte única de config)
  sessao.py            # conexão CDP / helpers de navegação
  ingestao.py          # planilha → dataclasses; lista fixa de matérias
  matching.py          # normalização de nomes e matching tolerante de classes
  harvester.py         # leitura/inspeção do Gestor de Classes (fora do fluxo do main na v1)
  perfil.py            # leitura/escrita no perfil do professor (CENSO) — 5 fases
  registro.py          # acumulador de log + export xlsx
  verificar_sessao.py  # smoke test de conexão CDP
  main.py              # orquestrador + fila de retry
dados/                 # entrada: input_professores.xlsx
logs/                  # saída: um xlsx por execução
docs/adr/              # decisões de arquitetura (ADRs)
```

## Decisões de arquitetura

As decisões estão documentadas em [`docs/adr/`](docs/adr/):

- **ADR-001** — Autenticação por CDP-attach com login manual (`AUTH_MODE`)
- **ADR-002** — API síncrona do Playwright
- **ADR-003** — Log de execução em xlsx (sem banco de dados)
- **ADR-004** — Harvest do GC e join por Persona ID (join vigente; harvest legado no fluxo v1)
- **ADR-005** — Matching tolerante de classes
- **ADR-006** — Currículo fixo em código (`ANOS_FIXOS` + `MATERIAS_PADRAO`)
- **ADR-007** — Idempotência por delta
- **ADR-008** — Fila de retry para professores com pendência
- **ADR-009** — Validação por confirmação de toast
- **ADR-010** — Seletores CSS/XPath locais a cada módulo
- **ADR-011** — Entrada centrada em planilha, sem banco de dados
