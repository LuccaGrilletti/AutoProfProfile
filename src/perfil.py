"""Leitura e escrita no perfil do professor (CENSO).

processar_professor() executa cinco fases:
  1. Deriva as matérias necessárias da lista fixa da planilha (`carregar_materias`); na v1 NÃO
     vêm do Gestor de Classes (ver ADR-006).
  2. Localiza o professor no CENSO (pelo login) → persona_id e lê o estado atual (turmas + matérias).
  3. Calcula o delta (o que falta).
  4. Escreve as turmas e matérias faltantes.
  5. Valida: como o portal não emite confirmação confiável ao salvar, considera "resolvido" apenas
     o que foi confirmado pelo toast "Salvo corretamente!" durante a escrita (Fase 4). O que não
     foi confirmado marca o professor como `parcial` (candidato a retry). Não há releitura do
     perfil — ver ADR-009.

Entry de debug (processa UM professor da planilha, com o Chrome logado):
    python -m src.perfil <login>
"""

from dataclasses import dataclass, field

from . import config
from .ingestao import AtribuicaoProfessor
from .matching import classe_bate, segmento_para_texto
from .registro import RegistroExecucao, resumir_erro
from time import sleep

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
ABA_TURMAS   = "//div[contains(@class,'mat-tab-label') and .//div[normalize-space()='Turmas']]"
ABA_MATERIAS = "//div[contains(@class,'mat-tab-label') and .//div[normalize-space()='Matérias']]"

# --- Seletores: edição. ":visible" garante o elemento da aba ativa (evita o gêmeo oculto). ---
BOTAO_EDITAR_TURMAS  = "button.btn.btn-primary.btn-sm.ml-2.ng-star-inserted:visible"
BOTAO_EDITAR_MATERIAS = "button.btn.btn-sm.btn-primary.float-right:visible"
# Edição de turmas: dois comboboxes visíveis simultaneamente.
# nth=0 → segmento; nth=1 → turma (fica clicável após selecionar o segmento).
COMBOBOX_SEGMENTO = "input[role='combobox']:visible >> nth=0"
COMBOBOX_TURMA = "input[role='combobox']:visible >> nth=1"
# Edição de matérias: único combobox visível naquele contexto.
COMBOBOX_MATERIA = "#field-materias"
# O dropdown do ng-select renderiza FORA do DOM do campo (portal) — seletor global, nunca scoped.
OPCAO_DROPDOWN = "div.ng-option.ng-star-inserted:visible"
BOTAO_ADICIONAR_TURMA = "button.btn.btn-warning.btn-sm.float-right.mt-2:visible"
BOTAO_SALVAR_TURMAS = "button.btn.btn-success.btn-sm.ml-2.ng-star-inserted:visible"
BOTAO_SALVAR_MATERIAS = "button.btn.btn-sm.btn-primary.float-right.ng-star-inserted:visible"
TOAST_SALVO = "h6.ng-star-inserted"  # toast "Salvo corretamente!" — única confirmação de save do portal

TIMEOUT_LEITURA = 12_000   # aba que pode estar legitimamente vazia
TIMEOUT_DROPDOWN = 8_000   # opções do ng-select após digitar


@dataclass
class ResultadoProfessor:
    """Resultado do processamento de um professor (uma execução de processar_professor)."""
    login: str
    # status final do professor:
    #   sucesso        — todo o delta foi adicionado e confirmado por toast
    #   ja_configurado — nada faltava (turmas e matérias já presentes)
    #   parcial        — parte do delta não foi confirmada (candidato a retry)
    #   nao_encontrado — login não retornou resultado na busca do CENSO
    #   erro           — exceção durante o processamento
    status: str
    turmas_adicionadas: list[str] = field(default_factory=list)
    materias_adicionadas: list[str] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)


def processar_professor(page, prof: AtribuicaoProfessor,
                        materias_fixas: list[tuple[str, str]],
                        url_censo: str, url_professor_base: str,
                        registro: RegistroExecucao) -> ResultadoProfessor:
    """Processa um professor de ponta a ponta e devolve o ResultadoProfessor.

    Executa as cinco fases descritas no docstring do módulo (buscar persona_id → ler estado →
    delta → escrever → validar por toast), registrando cada operação em `registro`. É idempotente:
    relê o estado atual e só escreve o delta, então pode ser chamada de novo com segurança (ADR-007).
    Nunca levanta exceção — falhas viram status `erro` no resultado e uma linha de erro no registro.
    """
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

        # Fase 1 — matérias necessárias a partir da lista fixa da planilha
        materias_necessarias = _derivar_materias(materias_fixas)

        # Fase 2b — abrir perfil e ler estado atual
        url_perfil = f"{url_professor_base}{persona_id}?nivelId={config.NIVEL_ID}"
        _abrir_perfil(page, url_perfil)
        turmas_atuais   = _ler_turmas_atuais(page)
        materias_atuais = _ler_materias_atuais(page)

        # Fase 3 — delta
        turmas_delta   = [a for a in prof.turmas if not _turma_presente(a, turmas_atuais)]
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
            _abrir_perfil(page, url_perfil)

        if materias_delta:
            _escrever_materias(page, materias_delta, prof, persona_id, resultado, registro)

        # Fase 5 — validação baseada no que foi confirmado pelo toast
        turmas_nao_resolvidas = [
            a for a in turmas_delta
            if a.chave_canonica not in resultado.turmas_adicionadas
        ]
        materias_nao_resolvidas = [
            (nome, serie) for nome, serie in materias_delta
            if f"{nome}: {serie}" not in resultado.materias_adicionadas
        ]

        if turmas_nao_resolvidas or materias_nao_resolvidas:
            resultado.status = "parcial"
            for alvo in turmas_nao_resolvidas:
                registro.registrar(login_professor=prof.login, persona_id=persona_id,
                                   fase="validacao", acao="turma_faltando",
                                   detalhe=alvo.chave_canonica, status="parcial")
            for nome, serie in materias_nao_resolvidas:
                registro.registrar(login_professor=prof.login, persona_id=persona_id,
                                   fase="validacao", acao="materia_faltando",
                                   detalhe=f"{nome}: {serie}", status="parcial")
        else:
            resultado.status = "sucesso"
            registro.registrar(login_professor=prof.login, persona_id=persona_id,
                               fase="validacao", acao="validado", status="sucesso",
                               detalhe=f"{len(turmas_delta)} turma(s) + {len(materias_delta)} matéria(s)")
        return resultado

    except Exception as exc:
        resultado.status = "erro"
        resultado.erros.append(resumir_erro(exc))
        registro.registrar_erro(exc, login_professor=prof.login, persona_id=persona_id, fase="perfil")
        return resultado

# --- Fase 1: derivar matérias do GC ---

def _derivar_materias(materias_fixas: list[tuple[str, str]]) -> set[tuple[str, str]]:
    """Retorna o conjunto fixo de matérias — fonte é a planilha, não o GC."""
    return set(materias_fixas)


# --- Fase 2: busca e leitura ---

def _buscar_persona_id(page, url_censo, login):
    """Busca o professor no CENSO pelo login e devolve o persona_id (ou None se não houver resultado).

    O persona_id é a chave que liga o login ao perfil do professor na URL (ver ADR-004).
    """
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
    """Lê a aba Turmas do perfil e devolve os textos das turmas atuais (ex.: '7° ano EF AF Turma G').

    Set vazio é resultado legítimo (professor ainda sem turmas) — a tabela pode não renderizar.
    """
    _clicar_aba(page, "Turmas")
    page.wait_for_load_state("networkidle", timeout=config.TIMEOUT_ELEMENTO)
    turmas = set()
    try:
        page.wait_for_selector(BOTAO_EDITAR_TURMAS, timeout=config.TIMEOUT_ELEMENTO)
        for linha in page.query_selector_all("tr.mat-row"):
            grado = linha.query_selector("td.cdk-column-grado")
            grupo = linha.query_selector("td.cdk-column-grupo")
            if grado and grupo:
                turmas.add(f"{grado.inner_text().strip()} {grupo.inner_text().strip()}")
    except Exception:
        pass  # Tabela vazia — professor sem turmas ainda, retorna set vazio normalmente
    return turmas


def _ler_materias_atuais(page) -> set[str]:
    """Lê a aba Matérias do perfil e devolve os rótulos atuais (formato 'Nome: série').

    Set vazio é resultado legítimo (professor ainda sem matérias).
    """
    _clicar_aba(page, "Matérias")
    page.wait_for_load_state("networkidle", timeout=config.TIMEOUT_ELEMENTO)
    try:
        page.wait_for_selector(BOTAO_EDITAR_MATERIAS, timeout=config.TIMEOUT_ELEMENTO)
        return {
            label.inner_text().strip()
            for label in page.query_selector_all("label.col-form-label.text-left")
        }
    except Exception:
        return set()  # Sem matérias ainda


# --- Fase 3: delta (lógica pura, testável) ---

def _norm(texto: str) -> str:
    """Colapsa espaços para comparação (normalização só de espaços, conforme escopo)."""
    return " ".join(texto.split())


def _turma_presente(alvo, turmas_textos) -> bool:
    """True se alguma turma atual (texto do portal) corresponde ao alvo via classe_bate."""
    return any(classe_bate(texto, alvo) for texto in turmas_textos)


def _materias_faltantes(necessarias: set[tuple], atuais: set[str]) -> list[tuple]:
    # atuais já vêm no formato "Nome: série" (ex: "Ciências: 7º ano EF AF")
    # necessarias são tuplas (nome, serie) → reconstruímos "nome: serie" para comparar
    atuais_norm = {_norm(m) for m in atuais}
    faltantes = [
        (nome, serie) for nome, serie in necessarias
        if _norm(f"{nome}: {serie}") not in atuais_norm
    ]
    return sorted(faltantes, key=lambda t: (t[1], t[0]))


# --- Fase 4: escrita ---
def _escrever_turmas(page, turmas_delta, prof, persona_id, resultado, registro):
    """Adiciona cada turma do delta na aba Turmas e salva uma vez no final.

    Para cada alvo, tenta selecioná-lo nos comboboxes (_selecionar_e_adicionar_turma); o que entra
    é registrado em `resultado.turmas_adicionadas` (base da validação da Fase 5). Só clica em salvar
    se ao menos uma turma foi adicionada, e espera o toast "Salvo corretamente!" aparecer e sumir.
    """
    _clicar_aba(page, "Turmas")
    page.click(BOTAO_EDITAR_TURMAS)
    page.wait_for_selector(COMBOBOX_SEGMENTO, timeout=config.TIMEOUT_ELEMENTO)
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
        try:
            page.wait_for_selector(TOAST_SALVO, timeout=config.TIMEOUT_ELEMENTO)
            page.wait_for_selector(TOAST_SALVO, state="hidden", timeout=config.TIMEOUT_ELEMENTO)
        except Exception:
            registro.registrar(login_professor=prof.login, persona_id=persona_id, fase="perfil",
                               acao="erro_save_turmas", status="erro",
                               detalhe="toast 'Salvo corretamente' não apareceu após salvar turmas")

def _selecionar_e_adicionar_turma(page, alvo) -> bool:
    """Seleciona segmento + turma nos dois comboboxes e clica em "Adicionar". True se adicionou.

    Padrão em dois passos porque o combobox de turma só fica utilizável após escolher o segmento:
    abre o dropdown de segmento (nth=0) e casa pelo texto; depois abre o de turma (nth=1) e percorre
    as opções usando `classe_bate` (sem digitar) até achar a que corresponde ao alvo.
    """
    # Passo 1 — abrir dropdown de segmento (nth=0) e selecionar por texto interno
    texto_segmento = segmento_para_texto(alvo)
    page.click(COMBOBOX_SEGMENTO)
    try:
        page.wait_for_selector(OPCAO_DROPDOWN, timeout=TIMEOUT_DROPDOWN)
    except Exception:
        return False
    selecionou_segmento = False
    for opcao in page.query_selector_all(OPCAO_DROPDOWN):
        if texto_segmento.lower() in opcao.inner_text().strip().lower():
            opcao.click()
            selecionou_segmento = True
            break
    if not selecionou_segmento:
        return False

    # Passo 2 — abrir dropdown de turma (nth=1) e percorrer opções sem injeção de texto
    page.click(COMBOBOX_TURMA)
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
    """Adiciona cada matéria do delta na aba Matérias e salva uma vez no final.

    Mesma lógica de _escrever_turmas: o que entra vai para `resultado.materias_adicionadas`
    (formato 'Nome: série'), base da validação da Fase 5.
    """
    sleep(0.5)
    _clicar_aba(page, "Matérias")
    page.wait_for_load_state("networkidle", timeout=config.TIMEOUT_ELEMENTO)
    page.wait_for_selector(BOTAO_EDITAR_MATERIAS, timeout=config.TIMEOUT_ELEMENTO)
    page.click(BOTAO_EDITAR_MATERIAS)
    page.wait_for_load_state("networkidle", timeout=config.TIMEOUT_ELEMENTO)
    page.wait_for_selector(COMBOBOX_MATERIA, timeout=config.TIMEOUT_ELEMENTO)
    adicionou = False
    for nome_materia, serie in materias_delta:
        if _selecionar_materia(page, nome_materia, serie):
            entrada = f"{nome_materia}: {serie}"
            resultado.materias_adicionadas.append(entrada)
            registro.registrar(login_professor=prof.login, persona_id=persona_id, fase="perfil",
                               acao="materia_adicionada", detalhe=entrada, status="sucesso")
            adicionou = True
        else:
            registro.registrar(login_professor=prof.login, persona_id=persona_id, fase="perfil",
                               acao="materia_nao_encontrada",
                               detalhe=f"{nome_materia}: {serie}", status="parcial")
    if adicionou:
        page.click(BOTAO_SALVAR_MATERIAS)


def _selecionar_materia(page, nome_materia: str, serie: str) -> bool:
    """Abre o dropdown de matérias e seleciona a opção que casa nome + série. True se selecionou.

    Cada opção tem o nome no text node e a série num <small>; casa por nome exato e série no sufixo
    do <small> (evita confundir a mesma matéria em séries diferentes).
    """
    seta = page.query_selector("#field-materias .ng-arrow-wrapper")
    if not seta:
        return False
    seta.click()
    try:
        page.wait_for_selector(OPCAO_DROPDOWN, timeout=TIMEOUT_DROPDOWN)
    except Exception:
        return False

    for opcao in page.query_selector_all(OPCAO_DROPDOWN):
        nome_opcao = opcao.evaluate("""el => {
            return Array.from(el.childNodes)
                .filter(n => n.nodeType === Node.TEXT_NODE)
                .map(n => n.textContent.trim())
                .filter(t => t.length > 0)
                .join('');
        }""")
        small = opcao.query_selector("small")
        small_opcao = small.inner_text().strip() if small else ""
        if nome_opcao == nome_materia.strip() and small_opcao.endswith(serie.strip()):
            opcao.click()
            return True
    return False


def _clicar_aba(page, texto_aba: str) -> None:
    """Clica na aba pelo texto via JS — contorna problemas de listener do Angular."""
    page.evaluate("""(texto) => {
        const abas = document.querySelectorAll('.mat-tab-label');
        for (const aba of abas) {
            if (aba.textContent.trim().includes(texto)) {
                aba.click();
                return;
            }
        }
    }""", texto_aba)
    page.wait_for_load_state("networkidle", timeout=30000)

# --- Entry de debug ---

def _debug(login: str) -> None:
    from .sessao import obter_sessao
    from .ingestao import carregar_planilha, carregar_materias

    profs = carregar_planilha(config.CAMINHO_PLANILHA)
    prof = next((p for p in profs if p.login == login), None)
    if prof is None:
        print(f"login '{login}' não encontrado em {config.CAMINHO_PLANILHA}")
        return

    materias_fixas = carregar_materias(config.CAMINHO_PLANILHA)
    registro = RegistroExecucao()
    pw = None
    try:
        pw, _browser, page = obter_sessao(config.AUTH_MODE, config.CDP_URL, config.URL_PEGASUS)
        resultado = processar_professor(page, prof, materias_fixas, config.URL_CENSO,
                                        config.URL_PROFESSOR_BASE, registro)
    finally:
        if pw is not None:
            pw.stop()

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
