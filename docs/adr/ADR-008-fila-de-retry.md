# ADR-008 — Fila de retry para professores com pendência

**Status:** Aceito

## Contexto

A escrita no portal depende de uma SPA Angular instável: dropdowns que demoram a renderizar, toasts
que às vezes não aparecem, navegações lentas. Uma turma ou matéria pode falhar de forma transitória
numa tentativa e funcionar na seguinte. Sem reprocessamento, o operador teria que caçar e repetir
manualmente cada pendência.

## Decisão

`main._processar_todos` mantém uma **fila de retry**:

1. Processa todos os professores; quem termina com status `parcial` ou `erro` (`STATUS_RETRY`)
   volta para a próxima rodada.
2. Repete até não haver pendentes **ou** atingir **`config.RETRY_MAX`** (padrão 3) tentativas.
3. Como `processar_professor` é idempotente (ADR-007) e relê o estado, cada nova tentativa enxerga
   o delta já reduzido — só tenta o que ainda falta.

O resultado final de cada professor é o da última tentativa; o resumo lista quem seguiu pendente.

## Consequências

- **+** Absorve falhas transitórias do portal sem intervenção manual.
- **+** Custo controlado por `RETRY_MAX`; sem loop infinito.
- **+** Combina naturalmente com a idempotência por delta.
- **−** Uma falha **determinística** (ex.: opção que não existe no dropdown) é repetida `RETRY_MAX`
  vezes antes de desistir — gasta tempo, mas o log deixa a causa explícita.
