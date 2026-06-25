# ADR-009 — Validação por confirmação de toast (por operação)

**Status:** Aceito — revisa o ponto 4 da ADR-005 ("validação pós-save por releitura").

## Contexto

O portal não emite uma confirmação confiável e global ao salvar. A ADR-005 previa **reler o perfil**
após salvar para conferir o que persistiu. Na prática, a releitura completa é cara (mais navegações)
e ainda sujeita às mesmas instabilidades de renderização da SPA — sem ganho proporcional. O sinal
disponível e mais barato é o toast **"Salvo corretamente!"** que aparece após cada save.

## Decisão

A validação é feita **durante a escrita**, por operação, não por releitura:

1. Ao adicionar uma turma/matéria com sucesso, ela é registrada em `resultado.turmas_adicionadas` /
   `resultado.materias_adicionadas`.
2. Após salvar, espera-se o toast `TOAST_SALVO` aparecer (e sumir). Se não aparecer, registra-se um
   erro de save para aquele bloco.
3. Na Fase 5, o que estava no delta mas **não** entrou em `*_adicionadas` marca o professor como
   `parcial` (candidato a retry — ADR-008). Tudo confirmado ⇒ `sucesso`.

Não há releitura do perfil; a verdade é o que foi confirmado no momento da escrita + o log (ADR-003).

## Consequências

- **+** Menos navegações por professor (sem reabrir o perfil só para conferir).
- **+** Cada turma/matéria tem um registro explícito de confirmada vs. faltando.
- **−** Confia-se no toast e no clique bem-sucedido como prova de persistência — não há checagem
  server-side independente. Se o portal mostrar o toast sem persistir, o erro só apareceria numa
  execução futura (que releria o estado pela idempotência — ADR-007).
- **−** Diverge da ADR-005 original; mantida a coerência marcando-a como revista.
