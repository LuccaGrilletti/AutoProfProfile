"""Leitura e escrita no perfil do professor (CENSO).

processar_professor() executa cinco fases:
  1. Deriva as matérias necessárias do mapa do GC (pelo persona_id).
  2. Localiza o professor no CENSO (pelo login) e lê o estado atual (turmas + matérias).
  3. Calcula o delta (o que falta).
  4. Escreve as turmas e matérias faltantes.
  5. Valida relendo o perfil após salvar (não há toast de confirmação no portal).

Entry de debug (processa UM professor da planilha, com o Chrome logado):
    python -m src.perfil <login>
"""

from dataclasses import dataclass, field

from . import config
from .harvester import MapaProfessorClasses
from .ingestao import AtribuicaoProfessor
from .matching import classe_bate
from .registro import RegistroExecucao, resumir_erro

# --- Seletores: busca no CENSO (Fase 2) ---
CAMPO_LOGIN = "input[data-placeholder='Login do Professor']"
BOTAO_PESQUISAR = "button.btn.btn-info.d-block.ml-auto.btn-sm"
LINHA_RESULTADO = "tr.mat-row.cdk-row.ng-star-inserted"
COL_PERSONA_ID = "td.cdk-column-personaId"

# --- Seletores: leitura do perfil ---
COL_GRADO = "td.cdk-column-grado"
COL_GRUPO = "td.cdk-column-grupo"
LINHA_TABELA = "tr.mat-row"
LABEL_MATERIA = "label.col-form-label.text-left"

# --- Seletores: abas (xpath pelo texto do label) ---
ABA_TURMAS = "//div[contains(@class,'mat-tab-label-content') and normalize-space()='Turmas']"
ABA_MATERIAS = "//div[contains(@class,'mat-tab-label-content') and normalize-space()='Matérias']"

# --- Seletores: edição. ":visible" garante o elemento da aba ativa (evita o gêmeo oculto). ---
BOTAO_EDITAR = "button.btn.btn-primary.btn-sm.ml-2.ng-star-inserted:visible"
COMBOBOX = "input[role='combobox']:visible"
# O dropdown do ng-select renderiza FORA do DOM do campo (portal) — seletor global, nunca scoped.
OPCAO_DROPDOWN = "div.ng-option.ng-star-inserted:visible"
BOTAO_ADICIONAR_TURMA = "button.btn.btn-warning.btn-sm.float-right.mt-2:visible"
BOTAO_SALVAR_TURMAS = "button.btn.btn-success.btn-sm.ml-2.ng-star-inserted:visible"
BOTAO_SALVAR_MATERIAS = "button.btn.btn-sm.btn-primary.float-right.ng-star-inserted:visible"

TIMEOUT_LEITURA = 12_000   # aba que pode estar legitimamente vazia
TIMEOUT_DROPDOWN = 8_000   # opções do ng-select após digitar


@dataclass
class ResultadoProfessor:
    login: str
    status: str                    # sucesso | parcial | erro | ja_configurado | nao_encontrado
    turmas_adicionadas: list[str] = field(default_factory=list)
    materias_adicionadas: list[str] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)


def processar_professor(page, prof: AtribuicaoProfessor, mapa_gc: MapaProfessorClasses,
                        url_censo: str, url_professor_base: str,
                        registro: RegistroExecucao) -> ResultadoProfessor:
    """Processa um professor (5 fases) e retorna o resultado, logando linha a linha."""
    resultado = ResultadoProfessor(login=prof.login, status="erro")
    persona_id = ""
    try:
        # Fase 2a — localizar pelo login → persona_id
        persona_id = _buscar_persona_id(page, url_censo, prof.login) or ""
        if not persona_id:
            resultado.status = "nao_encontrado"
            registro.registrar(login_professor=prof.login, fase="perfil", acao="nao_encontrado",
                               detalhe="login não retornou resultado na busca do CENSO",
                               status="nao_encontrado")
            return resultado

        # Fase 1 — matérias necessárias a partir do GC (cruzando pelo persona_id)
        materias_necessarias = _derivar_materias(prof, mapa_gc, persona_id, registro)

        # Fase 2b — abrir perfil e ler estado atual
        url_perfil = f"{url_professor_base}{persona_id}?nivelId={config.NIVEL_ID}"
        _abrir_perfil(page, url_perfil)
        turmas_atuais = _ler_turmas_atuais(page)
        materias_atuais = _ler_materias_atuais(page)

        # Fase 3 — delta
        turmas_delta = [a for a in prof.turmas if not _turma_presente(a, turmas_atuais)]
        materias_delta = _materias_faltantes(materias_necessarias, materias_atuais)

        if not turmas_delta and not materias_delta:
            resultado.status = "ja_configurado"
            registro.registrar(login_professor=prof.login, persona_id=persona_id, fase="perfil",
                               acao="ja_existia", detalhe="turmas e matérias já configuradas",
                               status="ja_configurado")
            return resultado

        # Fase 4 — escrever
        if turmas_delta:
            _escrever_turmas(page, turmas_delta, prof, persona_id, resultado, registro)
        if materias_delta:
            _escrever_materias(page, materias_delta, prof, persona_id, resultado, registro)

        # Fase 5 — validação pós-save (recarrega o perfil para ler o estado persistido)
        _abrir_perfil(page, url_perfil)
        turmas_faltando = [a for a in turmas_delta if not _turma_presente(a, _ler_turmas_atuais(page))]
        materias_faltando = _materias_faltantes(materias_delta, _ler_materias_atuais(page))

        if turmas_faltando or materias_faltando:
            resultado.status = "parcial"
            for alvo in turmas_faltando:
                registro.registrar(login_professor=prof.login, persona_id=persona_id,
                                   fase="validacao", acao="turma_faltando",
                                   detalhe=alvo.chave_canonica, status="parcial")
            for materia in materias_faltando:
                registro.registrar(login_professor=prof.login, persona_id=persona_id,
                                   fase="validacao", acao="materia_faltando",
                                   detalhe=materia, status="parcial")
        else:
            resultado.status = "sucesso"
            registro.registrar(login_professor=prof.login, persona_id=persona_id, fase="validacao",
                               acao="validado", status="sucesso",
                               detalhe=f"{len(turmas_delta)} turma(s) + {len(materias_delta)} matéria(s)")
        return resultado
    except Exception as exc:
        resultado.status = "erro"
        resultado.erros.append(resumir_erro(exc))
        registro.registrar_erro(exc, login_professor=prof.login, persona_id=persona_id, fase="perfil")
        return resultado


# --- Fase 1: derivar matérias do GC ---

def _derivar_materias(prof, mapa_gc, persona_id, registro) -> set[str]:
    """União das matérias das classes do GC (do professor) que casam com cada turma-alvo.

    Turma-alvo sem classe correspondente no GC → registra ambiguidade (não há matérias a derivar;
    a turma em si ainda pode ser adicionada, pois vem da planilha).
    """
    classes_prof = mapa_gc.get(persona_id, [])
    materias: set[str] = set()
    for alvo in prof.turmas:
        encontradas = [c for c in classes_prof if classe_bate(c.nome, alvo)]
        if not encontradas:
            registro.registrar(login_professor=prof.login, persona_id=persona_id, fase="perfil",
                               acao="ambiguidade", status="ambiguidade",
                               detalhe=f"sem classe no GC para {alvo.chave_canonica}")
            continue
        for classe in encontradas:
            materias |= classe.materias
    return materias


# --- Fase 2: busca e leitura ---

def _buscar_persona_id(page, url_censo, login):
    page.goto(url_censo, timeout=config.TIMEOUT_NAVEGACAO)
    page.wait_for_selector(CAMPO_LOGIN, timeout=config.TIMEOUT_ELEMENTO)
    page.fill(CAMPO_LOGIN, login)
    page.click(BOTAO_PESQUISAR)
    try:
        page.wait_for_selector(LINHA_RESULTADO, timeout=config.TIMEOUT_ELEMENTO)
    except Exception:
        return None  # nenhuma linha de resultado → não encontrado
    cell = page.query_selector(f"{LINHA_RESULTADO} {COL_PERSONA_ID}") or page.query_selector(COL_PERSONA_ID)
    return (cell.inner_text().strip() if cell else "") or None


def _abrir_perfil(page, url_perfil):
    """Navega para o perfil e espera as abas renderizarem (deixa na aba Turmas, a primeira)."""
    page.goto(url_perfil, timeout=config.TIMEOUT_NAVEGACAO)
    page.wait_for_selector(ABA_TURMAS, timeout=config.TIMEOUT_ELEMENTO)


def _ler_turmas_atuais(page) -> set[str]:
    """Lê a tabela de turmas (aba Turmas, modo leitura). Vazio se o professor não tiver turmas."""
    turmas = set()
    for linha in page.query_selector_all(LINHA_TABELA):
        grado_cell = linha.query_selector(COL_GRADO)
        if grado_cell is None:
            continue  # linha de outra tabela/aba
        grado = grado_cell.inner_text().strip()
        grupo_cell = linha.query_selector(COL_GRUPO)
        grupo = grupo_cell.inner_text().strip() if grupo_cell else ""
        texto = f"{grado} {grupo}".strip()
        if texto:
            turmas.add(texto)
    return turmas


def _ler_materias_atuais(page) -> set[str]:
    """Lê os rótulos de matérias (aba Matérias, modo leitura). Vazio se não houver matérias."""
    page.click(ABA_MATERIAS)
    try:
        page.wait_for_selector(LABEL_MATERIA, timeout=TIMEOUT_LEITURA)
    except Exception:
        return set()
    return {t for t in (lbl.inner_text().strip() for lbl in page.query_selector_all(LABEL_MATERIA)) if t}


# --- Fase 3: delta (lógica pura, testável) ---

def _norm(texto: str) -> str:
    """Colapsa espaços para comparação (normalização só de espaços, conforme escopo)."""
    return " ".join(texto.split())


def _turma_presente(alvo, turmas_textos) -> bool:
    """True se alguma turma atual (texto do portal) corresponde ao alvo via classe_bate."""
    return any(classe_bate(texto, alvo) for texto in turmas_textos)


def _materias_faltantes(necessarias, atuais) -> list[str]:
    """Matérias necessárias que não estão nas atuais (comparação normalizada por espaços)."""
    atuais_norm = {_norm(m) for m in atuais}
    return sorted(m for m in necessarias if _norm(m) not in atuais_norm)


# --- Fase 4: escrita ---

def _escrever_turmas(page, turmas_delta, prof, persona_id, resultado, registro):
    page.click(ABA_TURMAS)
    page.click(BOTAO_EDITAR)
    page.wait_for_selector(COMBOBOX, timeout=config.TIMEOUT_ELEMENTO)
    adicionou = False
    for alvo in turmas_delta:
        if _selecionar_e_adicionar_turma(page, alvo):
            resultado.turmas_adicionadas.append(alvo.chave_canonica)
            registro.registrar(login_professor=prof.login, persona_id=persona_id, fase="perfil",
                               acao="turma_adicionada", detalhe=alvo.chave_canonica, status="sucesso")
            adicionou = True
        else:
            registro.registrar(login_professor=prof.login, persona_id=persona_id, fase="perfil",
                               acao="turma_nao_encontrada", status="parcial",
                               detalhe=f"opção não localizada no dropdown para {alvo.chave_canonica}")
    if adicionou:
        page.click(BOTAO_SALVAR_TURMAS)


def _selecionar_e_adicionar_turma(page, alvo) -> bool:
    page.fill(COMBOBOX, alvo.chave_pesquisa)
    try:
        page.wait_for_selector(OPCAO_DROPDOWN, timeout=TIMEOUT_DROPDOWN)
    except Exception:
        return False
    for opcao in page.query_selector_all(OPCAO_DROPDOWN):
        if classe_bate(opcao.inner_text().strip(), alvo):
            opcao.click()
            page.click(BOTAO_ADICIONAR_TURMA)
            return True
    return False


def _escrever_materias(page, materias_delta, prof, persona_id, resultado, registro):
    page.click(ABA_MATERIAS)
    page.click(BOTAO_EDITAR)
    page.wait_for_selector(COMBOBOX, timeout=config.TIMEOUT_ELEMENTO)
    adicionou = False
    for materia in materias_delta:
        if _selecionar_materia(page, materia):
            resultado.materias_adicionadas.append(materia)
            registro.registrar(login_professor=prof.login, persona_id=persona_id, fase="perfil",
                               acao="materia_adicionada", detalhe=materia, status="sucesso")
            adicionou = True
        else:
            registro.registrar(login_professor=prof.login, persona_id=persona_id, fase="perfil",
                               acao="materia_nao_encontrada", detalhe=materia, status="parcial")
    if adicionou:
        page.click(BOTAO_SALVAR_MATERIAS)


def _selecionar_materia(page, nome_materia) -> bool:
    page.fill(COMBOBOX, nome_materia)
    try:
        page.wait_for_selector(OPCAO_DROPDOWN, timeout=TIMEOUT_DROPDOWN)
    except Exception:
        return False
    for opcao in page.query_selector_all(OPCAO_DROPDOWN):
        if opcao.inner_text().strip().startswith(nome_materia):
            opcao.click()
            return True
    return False


# --- Entry de debug ---

def _debug(login: str) -> None:
    from .sessao import obter_sessao
    from .ingestao import carregar_planilha
    from .harvester import harvest_gc

    profs = carregar_planilha(config.CAMINHO_PLANILHA)
    prof = next((p for p in profs if p.login == login), None)
    if prof is None:
        print(f"login '{login}' não encontrado em {config.CAMINHO_PLANILHA}")
        return

    registro = RegistroExecucao()
    pw = None
    try:
        pw, _browser, page = obter_sessao(config.AUTH_MODE, config.CDP_URL, config.URL_PEGASUS)
        print("Harvest do GC (necessário para derivar matérias)... pode levar um tempo.")
        mapa = harvest_gc(page, config.URL_GC, config.URL_CLASSE_BASE)
        resultado = processar_professor(page, prof, mapa, config.URL_CENSO,
                                        config.URL_PROFESSOR_BASE, registro)
    finally:
        if pw is not None:
            pw.stop()  # modo manual: NÃO fecha o Chrome do usuário

    print(f"\n=== RESULTADO {login} ===")
    print("status              :", resultado.status)
    print("turmas adicionadas  :", resultado.turmas_adicionadas)
    print("matérias adicionadas:", resultado.materias_adicionadas)
    print("erros               :", resultado.erros)
    print("log                 :", registro.exportar(config.DIR_LOGS))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("uso: python -m src.perfil <login>")
        sys.exit(1)
    _debug(sys.argv[1])
