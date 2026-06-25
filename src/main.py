"""Orquestrador: lê a planilha e processa cada professor.

Fluxo: conectar → carregar planilha → carregar matérias fixas → loop de professores com fila de
retry (até RETRY_MAX) → exportar o log da execução → encerrar a sessão.

    python -m src.main                  # execução completa
    python -m src.main --limite 1       # só o 1º professor (validação controlada)
    python -m src.main --teste          # atalho: processa só o 1º professor
"""

import argparse
import sys

from . import config
from .ingestao import carregar_planilha, carregar_materias
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
    parser.add_argument("--teste", action="store_true",
                        help="atalho: processa só o 1º professor")
    return parser.parse_args()


def _processar_todos(page, profs, materias_fixas, registro):
    """Processa todos os professores com fila de retry até RETRY_MAX tentativas."""
    resultados: dict[str, object] = {}
    pendentes = list(profs)
    for tentativa in range(1, config.RETRY_MAX + 1):
        if tentativa > 1:
            print(f"\n--- Retry {tentativa - 1}/{config.RETRY_MAX - 1}: "
                  f"{len(pendentes)} professor(es) ---")
        proxima_rodada = []
        for i, prof in enumerate(pendentes, start=1):
            print(f"[{tentativa}.{i}/{len(pendentes)}] {prof.login}...", end=" ", flush=True)
            resultado = processar_professor(page, prof, materias_fixas, config.URL_CENSO,
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
    """Conta quantos resultados há em cada status (para o resumo final)."""
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
    limite = 1 if args.teste else args.limite

    if not config.CAMINHO_PLANILHA.exists():
        print(f"ERRO: planilha não encontrada em {config.CAMINHO_PLANILHA}")
        sys.exit(1)

    profs = carregar_planilha(config.CAMINHO_PLANILHA)
    if limite is not None:
        profs = profs[:limite]
    if not profs:
        print("Planilha sem professores. Nada a fazer.")
        sys.exit(0)

    materias_fixas = carregar_materias(config.CAMINHO_PLANILHA)
    print(f"{len(profs)} professor(es) a processar, "
          f"{len(materias_fixas)} matéria(s) fixas (AUTH_MODE={config.AUTH_MODE}).")

    registro = RegistroExecucao()
    pw = None
    browser = None
    try:
        print(f"Conectando à sessão ({config.AUTH_MODE})...")
        pw, browser, page = obter_sessao(config.AUTH_MODE, config.CDP_URL, config.URL_PEGASUS)

        resultados = _processar_todos(page, profs, materias_fixas, registro)
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