# ADR-002 — API síncrona do Playwright

**Status:** Aceito

## Contexto

Os projetos irmãos usam a API **assíncrona** do Playwright (`async_playwright`, `await`), em
grande parte por causa da orquestração de login humanizado e de múltiplos contextos. Esta
automação tem um fluxo linear e de sessão única: ler o GC, depois processar professores um a um.

## Decisão

Usar a **API síncrona** (`playwright.sync_api.sync_playwright`). Sem `asyncio`, sem `await`.

## Consequências

- **+** Código mais simples e direto para um pipeline sequencial; mais fácil de ler e depurar.
- **+** Combina naturalmente com o CDP-attach (ADR-001), que abre uma única página.
- **−** Diverge do estilo async dos irmãos (reuso de código entre projetos é limitado ao *estilo*,
  não às chamadas de browser).
- **Regra:** nada de `time.sleep()` fixo — esperas sempre via `wait_for_selector` /
  `wait_for_function` / `wait_for_load_state`.
