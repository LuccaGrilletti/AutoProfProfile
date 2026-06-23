"""Orquestrador: lê a planilha, faz o harvest do GC uma vez e processa cada professor.

Fluxo: conectar → carregar planilha → harvest do GC (1×) → loop de professores com fila de
retry (até RETRY_MAX) → exportar o log da execução → encerrar a sessão.

    python -m src.main                       # execução completa
    python -m src.main --limite 1            # só o 1º professor (validação controlada)
    python -m src.main --harvest-limite 20   # harvest parcial (teste rápido; matérias incompletas)
"""

import argparse
import sys

from . import config
from .harvester import harvest_gc
from .ingestao import carregar_planilha
from .perfil import processar_professor
from .registro import RegistroExecucao, resumir_erro
from .sessao import obter_sessao

STATUS_RETRY = ("parcial", "erro")
ORDEM_STATUS = ("sucesso", "ja_configurado", "parcial", "nao_encontrado", "erro")


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Atribuição de turmas e matérias ao professor no Pegasus (CENSO).")
    parser.add_argument("--limite", type=int, default=None,
                        help="processa no máximo N professores (validação controlada)")
    parser.add_argument("--harvest-limite", type=int, default=None,
                        help="limita o harvest a N classes (teste rápido; matérias podem ficar incompletas)")
    return parser.parse_args()


def _processar_todos(page, profs, mapa, registro):
    """Processa todos os professores com fila de retry (nível professor) até RETRY_MAX tentativas."""
    resultados: dict[str, object] = {}  # login → ResultadoProfessor (último resultado)
    pendentes = list(profs)
    for tentativa in range(1, config.RETRY_MAX + 1):
        if tentativa > 1:
            print(f"\n--- Retry {tentativa - 1}/{config.RETRY_MAX - 1}: "
                  f"{len(pendentes)} professor(es) ---")
        proxima_rodada = []
        for i, prof in enumerate(pendentes, start=1):
            print(f"[{tentativa}.{i}/{len(pendentes)}] {prof.login}...", end=" ", flush=True)
            resultado = processar_professor(page, prof, mapa, config.URL_CENSO,
                                            config.URL_PROFESSOR_BASE, registro)
            resultados[prof.login] = resultado
            print(resultado.status)
            if resultado.status in STATUS_RETRY:
                proxima_rodada.append(prof)
        pendentes = proxima_rodada
        if not pendentes:
            break

    if pendentes:
        print(f"\n{len(pendentes)} professor(es) seguem com pendência após "
              f"{config.RETRY_MAX} tentativa(s).")
    return list(resultados.values())


def _contar(resultados) -> dict:
    totais = {status: 0 for status in ORDEM_STATUS}
    for resultado in resultados:
        totais[resultado.status] = totais.get(resultado.status, 0) + 1
    return totais


def _imprimir_resumo(resultados, totais):
    print("\n=== RESUMO ===")
    for status in ORDEM_STATUS:
        print(f"  {status:15}: {totais.get(status, 0)}")
    pendentes = [r for r in resultados if r.status in STATUS_RETRY]
    if pendentes:
        print("  pendentes:")
        for resultado in pendentes:
            detalhe = "; ".join(resultado.erros) if resultado.erros else ""
            print(f"    - {resultado.login} ({resultado.status}) {detalhe}".rstrip())


def _encerrar_sessao(pw, browser, auth_mode):
    """No modo manual NÃO fecha o Chrome do usuário; apenas solta o driver do Playwright."""
    try:
        if browser is not None and auth_mode == "auto":
            browser.close()
    finally:
        if pw is not None:
            pw.stop()


def main():
    args = _parse_args()

    if not config.CAMINHO_PLANILHA.exists():
        print(f"ERRO: planilha não encontrada em {config.CAMINHO_PLANILHA}")
        sys.exit(1)

    profs = carregar_planilha(config.CAMINHO_PLANILHA)
    if args.limite is not None:
        profs = profs[:args.limite]
    if not profs:
        print("Planilha sem professores. Nada a fazer.")
        sys.exit(0)
    print(f"{len(profs)} professor(es) a processar (AUTH_MODE={config.AUTH_MODE}).")

    registro = RegistroExecucao()
    pw = None
    browser = None
    try:
        print(f"Conectando à sessão ({config.AUTH_MODE})...")
        pw, browser, page = obter_sessao(config.AUTH_MODE, config.CDP_URL, config.URL_PEGASUS)

        print("Lendo o Gestor de Classes (harvest único)...")
        mapa = harvest_gc(page, config.URL_GC, config.URL_CLASSE_BASE,
                          limite_classes=args.harvest_limite)

        resultados = _processar_todos(page, profs, mapa, registro)
        _imprimir_resumo(resultados, _contar(resultados))
    except Exception as exc:
        print(f"ERRO fatal: {resumir_erro(exc)}")
        registro.registrar_erro(exc, fase="execucao")
    finally:
        caminho_log = registro.exportar(config.DIR_LOGS)
        print(f"Log exportado: {caminho_log}")
        _encerrar_sessao(pw, browser, config.AUTH_MODE)


if __name__ == "__main__":
    main()
