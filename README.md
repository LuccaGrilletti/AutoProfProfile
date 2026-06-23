# AtribuiçãoProfessor

Automação (Python + Playwright) que atribui **turmas e matérias** ao perfil de cada professor no
**CENSO** do portal Pegasus (`apps.uno-internacional.com`).

O fluxo lê o **Gestor de Classes (GC)** uma única vez para montar um mapa
`professor → classes → matérias`, lê uma planilha com as turmas-alvo de cada professor e escreve
no CENSO **apenas o que estiver faltando** (delta), validando o resultado relendo o perfil após salvar.

## Autenticação (`AUTH_MODE`)

O modo de autenticação é controlado pela variável `AUTH_MODE` no `.env`:

- **`manual` (padrão):** você abre o Chrome com depuração remota e faz login **manualmente** antes
  de rodar o script. O script se anexa à sessão já autenticada via CDP.
- **`auto` (a implementar):** o script abriria o próprio Chrome e faria o login. Ainda é um stub
  (`NotImplementedError`).

### Abrir o Chrome para o modo manual

```
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome_pegasus_dev"
```

Faça login no Pegasus nessa janela antes de rodar o script.

## Instalação

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

> **Nota sobre `playwright install`:** no modo `manual` o script **anexa-se ao seu Chrome** via CDP —
> o navegador embutido do Playwright **não** é usado, então `playwright install chromium` é opcional.
> Ele só será necessário para o futuro modo `auto`.

## Configuração

Copie `.env.example` para `.env` e ajuste:

| Variável | Descrição |
|---|---|
| `COLEGIO_ID` | id do colégio (ex.: 29457) |
| `CICLO_ID` | ano letivo corrente — **atualizar anualmente** |
| `NIVEL_ID` | `nivelId` da URL do professor (33 funciona mesmo quando o portal indica 32) |
| `URL_PEGASUS` / `URL_BASE` | endpoints do portal |
| `CDP_URL` | endereço da depuração remota do Chrome (`http://localhost:9222`) |
| `AUTH_MODE` | `manual` ou `auto` |
| `RETRY_MAX` | tentativas por professor com status parcial/erro/ambiguidade |

## Uso

1. Abra o Chrome com depuração remota e faça login (ver acima).
2. **Valide a sessão** (smoke test):
   ```powershell
   .venv\Scripts\python -m src.verificar_sessao
   ```
3. Preencha `dados/input_professores.xlsx` (uma linha por professor — ver formato abaixo).
4. Rode o fluxo completo:
   ```powershell
   .venv\Scripts\python -m src.main
   ```
5. Confira o log da execução em `logs/atribuicao_AAAAMMDD_HHMM.xlsx`.

## Planilha de entrada (`dados/input_professores.xlsx`)

Uma linha por professor (linhas com o mesmo `login` são unidas). Colunas de ano com `"Sim"`
indicam os anos que o professor leciona naquela `turma`+`periodo`.

| login | turma | periodo | 1° EF | … | 9° EF | 1° EM | 2° EM | 3° EM |
|---|---|---|---|---|---|---|---|---|
| mirela.godoy | G | Matutino | | | Sim | Sim | | Sim |

## Desenvolvimento

```powershell
.venv\Scripts\python -m pytest
```

Os módulos de lógica pura (`matching`, `ingestao`, `registro`) são cobertos por testes que não
precisam de navegador.

## Estrutura

```
src/
  config.py        # .env + URLs derivadas + constantes
  sessao.py        # conexão CDP / helpers de navegação
  ingestao.py      # planilha → dataclasses
  matching.py      # normalização de nomes e filtro de classes
  harvester.py     # leitura completa do Gestor de Classes
  perfil.py        # leitura/escrita no perfil do professor (CENSO)
  registro.py      # acumulador de log + export xlsx
  verificar_sessao.py  # smoke test de conexão CDP
  main.py          # orquestrador
```

Decisões de arquitetura em [`docs/adr/`](docs/adr/).
