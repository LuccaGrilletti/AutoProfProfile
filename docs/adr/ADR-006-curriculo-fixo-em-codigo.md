# ADR-006 — Currículo fixo em código (ANOS_FIXOS + MATERIAS_PADRAO)

**Status:** Aceito (v1) — substitui, no fluxo principal, a derivação de matérias do GC descrita na
ADR-004.

## Contexto

A intenção original era derivar, por professor, quais anos ele leciona (colunas de ano da planilha,
marcadas com `"Sim"`) e quais matérias (cruzando com o Gestor de Classes via Persona ID — ADR-004).
Na prática, para a v1 o colégio tem um conjunto **estável e conhecido** de anos e de matérias por
série, e a leitura do GC é cara e suscetível a variações de DOM. Fazer o caminho completo (Sim por
professor + harvest do GC) adicionava risco e tempo sem ganho real para a primeira entrega.

## Decisão

A v1 trata o currículo como **fixo, definido em código**:

1. **Turmas:** `ingestao.carregar_planilha` ignora as colunas de ano da planilha e gera, para cada
   linha `login`+`turma`+`periodo`, uma `TurmaAlvo` por ano de **`config.ANOS_FIXOS`**
   (`[(1,EF),(5,EF),(6,EF),(7,EF),(1,EM),(3,EM)]`). A planilha só informa o **login**, a **turma**
   (letra) e o **período** de cada professor.
2. **Matérias:** `ingestao.carregar_materias` usa a aba `Materias` da planilha se existir; senão,
   a lista fixa **`MATERIAS_PADRAO`** (pares `nome, série`). O Gestor de Classes **não** alimenta
   esse passo na v1.

As colunas de ano (`COLUNAS_ANOS`) e o harvest do GC permanecem como **legado/ferramenta**, não no
caminho crítico.

## Consequências

- **+** Fluxo determinístico, rápido e sem dependência da leitura cara/instável do GC.
- **+** Planilha de entrada mínima (login, turma, período).
- **+** Currículo num único lugar, fácil de revisar.
- **−** Mudança de currículo (anos ou matérias) exige editar `config.ANOS_FIXOS` /
  `MATERIAS_PADRAO` (ou a aba `Materias`) — não é configurável por professor.
- **−** Todo professor recebe o mesmo conjunto de anos por turma/período; casos atípicos não são
  expressáveis sem voltar ao modelo por `"Sim"`/GC.
- **−** Há código legado (colunas de ano, `harvester` no fluxo) que pode confundir quem lê — por
  isso está marcado como tal no código e nas ADRs.
