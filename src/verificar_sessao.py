"""Smoke test da sessão CDP (modo manual).

Conecta ao Chrome já aberto e logado, confirma a aba do Pegasus, navega até o Gestor de Classes
e verifica que a tabela carrega. Rode com o Chrome aberto em --remote-debugging-port=9222 ANTES
de executar o fluxo completo:

    python -m src.verificar_sessao
"""

import sys

from . import config
from .sessao import obter_sessao


def _resumir_erro(excecao: Exception) -> str:
    """Achata e trunca a mensagem (erros do Playwright trazem call log extenso)."""
    return " ".join(str(excecao).split())[:300]


def main() -> int:
    print(f"Conectando via CDP em {config.CDP_URL} (AUTH_MODE={config.AUTH_MODE})...")
    pw = None
    try:
        pw, browser, page = obter_sessao(config.AUTH_MODE, config.CDP_URL, config.URL_PEGASUS)
    except Exception as exc:
        print(f"FALHA ao conectar: {_resumir_erro(exc)}")
        print("Verifique se o Chrome está aberto com:")
        print('  chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\chrome_pegasus_dev"')
        return 1

    try:
        print(f"Conectado. Aba atual: {page.title()!r} -> {page.url}")
        print(f"Navegando para o Gestor de Classes: {config.URL_GC}")
        page.goto(config.URL_GC, timeout=config.TIMEOUT_NAVEGACAO)
        page.wait_for_selector("table.mat-table.cdk-table.mat-sort", timeout=config.TIMEOUT_ELEMENTO)
        print("OK — tabela do Gestor de Classes carregada. Sessão válida.")
        return 0
    except Exception as exc:
        print(f"FALHA ao abrir o Gestor de Classes: {_resumir_erro(exc)}")
        print("A sessão pode não estar logada, ou COLEGIO_ID/CICLO_ID no .env estão errados.")
        return 1
    finally:
        # Em modo manual NÃO fechamos o Chrome do usuário; apenas soltamos o driver do Playwright.
        if pw is not None:
            pw.stop()


if __name__ == "__main__":
    sys.exit(main())
