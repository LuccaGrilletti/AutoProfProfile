from src.harvester import ClasseGC
from src.ingestao import AtribuicaoProfessor, TurmaAlvo
from src.perfil import _derivar_materias, _materias_faltantes, _turma_presente
from src.registro import RegistroExecucao


def _classe(nome, materias):
    return ClasseGC(id="x", nome=nome, materias=set(materias))


# --- Fase 1: derivar matérias do GC ---

def test_derivar_materias_uniao_das_classes_que_casam():
    prof = AtribuicaoProfessor(login="p", turmas=[
        TurmaAlvo(7, "EF", "G", "Matutino"),
        TurmaAlvo(1, "EM", "G", "Matutino"),
    ])
    mapa = {"123": [
        _classe("7° ano EF AF Turma G - Matutino", ["Matemática", "Física"]),
        _classe("1ª série EM Turma G - Matutino", ["Química"]),
        _classe("8° ano EF AF Turma G - Matutino", ["História"]),  # não casa nenhum alvo
    ]}
    reg = RegistroExecucao()
    materias = _derivar_materias(prof, mapa, "123", reg)
    assert materias == {"Matemática", "Física", "Química"}
    assert all(linha["acao"] != "ambiguidade" for linha in reg.linhas)


def test_derivar_materias_registra_ambiguidade_quando_sem_classe():
    prof = AtribuicaoProfessor(login="p", turmas=[TurmaAlvo(9, "EF", "Z", "Vespertino")])
    reg = RegistroExecucao()
    materias = _derivar_materias(prof, {"123": []}, "123", reg)
    assert materias == set()
    assert any(linha["acao"] == "ambiguidade" for linha in reg.linhas)


def test_derivar_materias_professor_ausente_no_mapa():
    prof = AtribuicaoProfessor(login="p", turmas=[TurmaAlvo(7, "EF", "G", "Matutino")])
    reg = RegistroExecucao()
    # persona_id sem entrada no mapa → nenhuma matéria + ambiguidade
    assert _derivar_materias(prof, {}, "999", reg) == set()
    assert any(linha["acao"] == "ambiguidade" for linha in reg.linhas)


# --- Fase 3: delta ---

def test_turma_presente_usa_classe_bate():
    alvo = TurmaAlvo(7, "EF", "G", "Matutino")
    assert _turma_presente(alvo, {"7° ano EF AF Turma G - Matutino"}) is True
    assert _turma_presente(alvo, {"7° ano EF AF Turma H - Matutino"}) is False
    assert _turma_presente(alvo, set()) is False


def test_materias_faltantes_detecta_ausentes():
    assert _materias_faltantes({"Matemática", "Física"}, {"Matemática"}) == ["Física"]


def test_materias_faltantes_normaliza_espacos():
    necessarias = {"Matemática", "Língua  Portuguesa"}  # dois espaços
    atuais = {"Matemática", "Língua Portuguesa"}         # um espaço
    assert _materias_faltantes(necessarias, atuais) == []


def test_materias_faltantes_tudo_presente():
    assert _materias_faltantes(set(), {"Matemática"}) == []
