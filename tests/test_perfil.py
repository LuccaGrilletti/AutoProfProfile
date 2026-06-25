"""Testes da lógica pura do perfil (sem navegador): Fase 1 (derivar matérias) e Fase 3 (delta).

Reflete o comportamento da v1: as matérias vêm da lista fixa (não do GC) e são pares (nome, série);
o delta de turmas usa classe_bate e o de matérias compara "Nome: série" normalizando espaços.
"""

from src.ingestao import TurmaAlvo
from src.perfil import _derivar_materias, _materias_faltantes, _turma_presente


# --- Fase 1: derivar matérias (da lista fixa) ---

def test_derivar_materias_retorna_conjunto_da_lista_fixa():
    fixas = [("Matemática", "7º ano EF AF"), ("Física", "1º ano EM")]
    assert _derivar_materias(fixas) == {("Matemática", "7º ano EF AF"), ("Física", "1º ano EM")}


def test_derivar_materias_remove_duplicatas():
    fixas = [("Matemática", "1º ano EM"), ("Matemática", "1º ano EM")]
    assert _derivar_materias(fixas) == {("Matemática", "1º ano EM")}


# --- Fase 3: delta de turmas ---

def test_turma_presente_usa_classe_bate():
    alvo = TurmaAlvo(7, "EF", "G", "Matutino")
    assert _turma_presente(alvo, {"7° ano EF AF Turma G - Matutino"}) is True
    assert _turma_presente(alvo, {"7° ano EF AF Turma H - Matutino"}) is False
    assert _turma_presente(alvo, set()) is False


# --- Fase 3: delta de matérias ---

def test_materias_faltantes_detecta_ausentes():
    necessarias = {("Matemática", "7º ano EF AF"), ("Física", "1º ano EM")}
    atuais = {"Matemática: 7º ano EF AF"}
    assert _materias_faltantes(necessarias, atuais) == [("Física", "1º ano EM")]


def test_materias_faltantes_normaliza_espacos():
    necessarias = {("Língua Portuguesa", "1º ano EF AI")}
    atuais = {"Língua  Portuguesa: 1º ano EF AI"}  # dois espaços no texto do portal
    assert _materias_faltantes(necessarias, atuais) == []


def test_materias_faltantes_tudo_presente():
    assert _materias_faltantes(set(), {"Matemática: 1º ano EM"}) == []


def test_materias_faltantes_ordenado_por_serie_e_nome():
    necessarias = {("Matemática", "3º ano EM"), ("Arte", "3º ano EM"), ("Física", "1º ano EM")}
    assert _materias_faltantes(necessarias, set()) == [
        ("Física", "1º ano EM"),
        ("Arte", "3º ano EM"),
        ("Matemática", "3º ano EM"),
    ]
