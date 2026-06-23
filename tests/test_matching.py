from src.ingestao import TurmaAlvo
from src.matching import classe_bate, normalizar_classe, periodo_bate


def test_normalizar_classe_extrai_ano_e_segmento():
    assert normalizar_classe("5º ano EFAI") == (5, "EF")
    assert normalizar_classe("6º ano EF AF") == (6, "EF")
    assert normalizar_classe("1ª série EM") == (1, "EM")
    assert normalizar_classe("5º EFAI") == (5, "EF")
    assert normalizar_classe("3ª série EM") == (3, "EM")


def test_normalizar_classe_sem_numero():
    assert normalizar_classe("ano EF") == (None, "EF")


def test_periodo_bate_exato():
    assert periodo_bate("7° ano EF AF Turma G - Matutino", "Matutino") is True
    assert periodo_bate("7° ano EF AF Turma G - Vespertino", "Matutino") is False


def test_classe_bate_positivo():
    alvo = TurmaAlvo(ano=7, segmento="EF", turma="G", periodo="Matutino")
    # texto no formato do portal (grado + grupo)
    assert classe_bate("7° ano EF AF Turma G - Matutino", alvo) is True
    # também casa contra o próprio texto canônico do alvo
    assert classe_bate(alvo.chave_canonica, alvo) is True


def test_classe_bate_negativos():
    alvo = TurmaAlvo(ano=7, segmento="EF", turma="G", periodo="Matutino")
    assert classe_bate("8° ano EF AF Turma G - Matutino", alvo) is False    # ano errado
    assert classe_bate("7° ano EF AF Turma H - Matutino", alvo) is False    # turma errada
    assert classe_bate("7° ano EF AF Turma G - Vespertino", alvo) is False  # período errado
    assert classe_bate("7ª série EM Turma G - Matutino", alvo) is False     # segmento errado


def test_classe_bate_em():
    alvo = TurmaAlvo(ano=1, segmento="EM", turma="A", periodo="Matutino")
    assert classe_bate("1ª série EM Turma A - Matutino", alvo) is True
    assert classe_bate("1° ano EF AF Turma A - Matutino", alvo) is False
