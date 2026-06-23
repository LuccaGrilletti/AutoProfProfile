# ADR-001 — Autenticação por CDP-attach com login manual (AUTH_MODE)

**Status:** Aceito

## Contexto

O portal Pegasus fica atrás do mesmo stack de identidade dos projetos irmãos
(`AutoAtribuicaoLMS`, `ModernaCOREAutoCheck`), que enfrentam reCAPTCHA v3 e investem pesado em
mitigação (Chrome real, stealth, digitação humanizada, warmup no Google, perfil persistente).
Essa luta é frágil e cara de manter.

## Decisão

A automação **não faz login**. O usuário abre o Chrome com depuração remota e faz login
manualmente; o script se **anexa via CDP** (`playwright.chromium.connect_over_cdp`) à sessão já
autenticada. O modo é controlado por `AUTH_MODE` no `.env`:

- `manual` (padrão): anexa à sessão existente.
- `auto` (futuro): abriria o próprio Chrome e faria login — hoje é um stub `NotImplementedError`
  em `sessao._sessao_automatizada`, pronto para ser preenchido sem tocar no resto.

## Consequências

- **+** Elimina por completo a briga com o reCAPTCHA; código de sessão trivial e robusto.
- **+** A troca `manual`↔`auto` é só uma variável de ambiente — nenhuma outra mudança de código.
- **−** Exige um passo manual antes de rodar (abrir o Chrome com `--remote-debugging-port=9222` e logar).
- **Regra:** no modo manual o script **nunca** fecha o navegador do usuário — apenas dá `pw.stop()`.
