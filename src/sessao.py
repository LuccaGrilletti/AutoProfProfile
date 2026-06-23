"""Sessão do navegador: conexão CDP (modo manual) ou login automatizado (modo auto, futuro).

Ponto de entrada único: obter_sessao(). O AUTH_MODE decide a estratégia; o restante do código
não precisa saber qual está ativa.
"""

from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from . import config


def obter_sessao(auth_mode: str, cdp_url: str, url_pegasus: str):
    """Retorna (playwright, browser, page) prontos para uso.

    auth_mode: "manual" (sessão CDP já aberta) | "auto" (login automatizado — a implementar).
    """
    if auth_mode == "manual":
        return _sessao_cdp(cdp_url, url_pegasus)
    elif auth_mode == "auto":
        return _sessao_automatizada(url_pegasus)
    else:
        raise ValueError(f"AUTH_MODE inválido: '{auth_mode}'. Use 'manual' ou 'auto'.")


def _sessao_cdp(cdp_url: str, url_pegasus: str):
    """Conecta ao Chrome iniciado com --remote-debugging-port=9222.

    O usuário já fez login manualmente antes de rodar o script. Seleciona a aba já aberta no
    host do Pegasus; se não houver, usa a primeira aba; se não houver nenhuma, cria uma nova.
    """
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(cdp_url)
    if not browser.contexts:
        pw.stop()
        raise RuntimeError(
            f"Nenhum contexto encontrado via CDP em {cdp_url}. "
            "O Chrome está aberto com --remote-debugging-port=9222?"
        )
    contexto = browser.contexts[0]
    page = _selecionar_pagina_pegasus(contexto, url_pegasus)
    return pw, browser, page


def _selecionar_pagina_pegasus(contexto, url_pegasus: str):
    """Escolhe a aba já aberta no host do Pegasus; senão a primeira; senão cria uma nova."""
    host = urlsplit(url_pegasus).netloc
    for pagina in contexto.pages:
        if urlsplit(pagina.url).netloc == host:
            return pagina
    if contexto.pages:
        return contexto.pages[0]
    return contexto.new_page()


def _sessao_automatizada(url_pegasus: str):
    """Abre o Chrome, navega para o Pegasus e executa o fluxo de login.

    AUTH_MODE=auto — implementar quando a estratégia de auth estiver definida.
    """
    raise NotImplementedError(
        "Modo 'auto' ainda não implementado. Use AUTH_MODE=manual e inicie o Chrome "
        'manualmente com --remote-debugging-port=9222 --user-data-dir="C:\\chrome_pegasus_dev".'
    )
    # Esqueleto para preenchimento futuro:
    # pw = sync_playwright().start()
    # browser = pw.chromium.launch(channel="chrome", headless=False)
    # context = browser.new_context()
    # page = context.new_page()
    # page.goto(url_pegasus)
    # _realizar_login(page)   # a implementar em auth.py
    # return pw, browser, page


def aguardar_elemento(page, seletor: str, timeout: int = config.TIMEOUT_ELEMENTO):
    """Aguarda elemento visível. Levanta erro com mensagem clara em caso de timeout."""
    try:
        page.wait_for_selector(seletor, timeout=timeout)
    except Exception as exc:
        raise TimeoutError(f"Elemento não encontrado após {timeout}ms: {seletor}") from exc


def scroll_para_elemento(page, seletor: str):
    """scrollIntoView via JS, se o elemento existir."""
    elemento = page.query_selector(seletor)
    if elemento:
        elemento.evaluate("el => el.scrollIntoView({behavior: 'smooth', block: 'center'})")


def aguardar_carregamento(page, timeout: int = 10_000):
    """Aguarda a rede estabilizar.

    Em SPA Angular o networkidle pode ser instável (long-polling) — prefira wait_for_selector
    no conteúdo-alvo. Use este helper com parcimônia.
    """
    page.wait_for_load_state("networkidle", timeout=timeout)
