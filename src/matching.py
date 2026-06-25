"""Normalização de nomes de classes e filtro de correspondência com TurmaAlvo.

A mesma função `classe_bate` é usada em três lugares: derivar matérias do GC, calcular o delta de
turmas do perfil e selecionar a opção certa no dropdown — por isso ela tolera as variações de texto
do portal ('5º ano EFAI', '1ª série EM', etc.).
"""

import re

from .ingestao import TurmaAlvo

# A preencher após validação — por ora matching exato apenas.
ALIASES_PERIODO: dict[str, list[str]] = {
    # Exemplo futuro: "Matutino": ["Matutino", "MAT"]
}


def normalizar_classe(texto: str) -> tuple[int | None, str]:
    """Extrai (ano, segmento) do texto da classe, tolerando variações.

    Ex.: '5º ano EFAI', '6º ano EF AF', '1ª série EM', '5º EFAI'.
    - Segmento: "EM" se "EM" presente no texto (case-insensitive), senão "EF".
    - Ano: primeiro número encontrado.
    Retorna (None, "EF") se não houver número.
    """
    match = re.search(r"(\d+)", texto)
    ano = int(match.group(1)) if match else None
    segmento = "EM" if "EM" in texto.upper() else "EF"
    return ano, segmento


def periodo_bate(texto: str, periodo: str) -> bool:
    """Verifica se o período do alvo está presente no texto da classe.

    Usa ALIASES_PERIODO se definido para o período, senão matching exato.
    """
    aliases = ALIASES_PERIODO.get(periodo, [periodo])
    return any(alias in texto for alias in aliases)


def classe_bate(texto_classe: str, alvo: TurmaAlvo) -> bool:
    """True se texto_classe corresponde ao TurmaAlvo (ano, segmento, turma e período)."""
    ano, segmento = normalizar_classe(texto_classe)
    return (
        ano == alvo.ano
        and segmento == alvo.segmento
        and f"Turma {alvo.turma}" in texto_classe
        and periodo_bate(texto_classe, alvo.periodo)
    )


def segmento_para_texto(alvo: TurmaAlvo) -> str:
    """Texto do segmento conforme aparece no dropdown do portal.

    Regra: anos 1–5 EF → Anos Iniciais; anos 6–9 EF → Anos Finais; EM → Ensino Médio.
    """
    if alvo.segmento == "EM":
        return "Ensino Médio"
    return "Ensino Fundamental Anos Iniciais" if alvo.ano <= 5 else "Ensino Fundamental Anos Finais"

def texto_small_esperado(alvo: TurmaAlvo) -> str:
    """Subtexto do <small> no dropdown de matérias do perfil, derivado do TurmaAlvo."""
    if alvo.segmento == "EM":
        return f"Ensino Médio: {alvo.ano}º ano EM"
    if alvo.ano <= 5:
        return f"Ensino Fundamental Anos Iniciais: {alvo.ano}º ano EF AI"
    return f"Ensino Fundamental Anos Finais: {alvo.ano}º ano EF AF"

