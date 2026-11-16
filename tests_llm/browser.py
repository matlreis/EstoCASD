"""
Ferramentas do navegador para o teste cego por LLM.
O modelo só enxerga a página pela árvore de acessibilidade (o que um leitor de tela leria), com
cada elemento numerado ([ref=e7]), e age por essas referências. Ele nunca vê o HTML nem o código.
"""
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# limite do snapshot em caracteres para caber no contexto de modelos menores
LIMITE_SNAPSHOT = 12000
# tempo máximo de cada ação (ms)
TEMPO_MAXIMO = 5000

# O navegador bloqueia o envio de um formulário com campo inválido (ex.: quantidade abaixo do
# mínimo) e mostra só um balão, que não entra no snapshot. Este script, rodado em toda página,
# guarda a mensagem do balão para o ler_pagina repassar ao modelo.
GUARDAR_AVISOS_JS = """
addEventListener('invalid', (evento) => {
    const campo = evento.target;
    const rotulo = campo.labels?.[0]?.innerText ?? campo.name;
    (window.avisosNavegador ??= []).push(`${rotulo} ${campo.validationMessage}`);
}, true);
"""
LER_AVISOS_JS = '() => { const avisos = window.avisosNavegador ?? []; window.avisosNavegador = []; return avisos; }'

# Schemas das ferramentas no formato de chat completions (compatível com OpenAI/OpenRouter)
FERRAMENTAS = [
    {
        'type': 'function',
        'function': {
            'name': 'ler_pagina',
            'description': 'Lê a página atual: URL, título e elementos visíveis, cada um com uma referência [ref=...].',
            'parameters': {'type': 'object', 'properties': {}, 'required': []},
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'navegar',
            'description': 'Abre um endereço do site, como se fosse digitado na barra do navegador.',
            'parameters': {
                'type': 'object',
                'properties': {'caminho': {'type': 'string', 'description': 'Caminho no site, ex.: /login/'}},
                'required': ['caminho'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'clicar',
            'description': 'Clica em um elemento da página (link, botão etc.).',
            'parameters': {
                'type': 'object',
                'properties': {'ref': {'type': 'string', 'description': 'Referência do elemento, ex.: e7'}},
                'required': ['ref'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'preencher',
            'description': 'Apaga o conteúdo de um campo e digita um valor. Datas no formato AAAA-MM-DD.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'ref': {'type': 'string', 'description': 'Referência do campo, ex.: e13'},
                    'valor': {'type': 'string', 'description': 'Texto a digitar'},
                },
                'required': ['ref', 'valor'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'voltar',
            'description': 'Volta para a página anterior, como o botão "voltar" do navegador.',
            'parameters': {'type': 'object', 'properties': {}, 'required': []},
        },
    },
]


class Navegador:
    """Executa no Playwright as ações pedidas pelo modelo e devolve a página resultante como texto."""

    def __init__(self, page, base_url):
        self.page = page
        self.base_url = base_url
        self.dialogos = []
        page.set_default_timeout(TEMPO_MAXIMO)
        # aceitar diálogos do site por padrão
        page.on('dialog', self._aceitar_dialogo)
        page.add_init_script(GUARDAR_AVISOS_JS)

    def _aceitar_dialogo(self, dialogo):
        self.dialogos.append(dialogo.message)
        dialogo.accept()

    def executar(self, nome, argumentos):
        """Executa a ferramenta `nome`. Erros voltam como texto, para o modelo corrigir e seguir."""
        acoes = {
            'ler_pagina': self.ler_pagina,
            'navegar': self.navegar,
            'clicar': self.clicar,
            'preencher': self.preencher,
            'voltar': self.voltar,
        }
        if nome not in acoes:
            return f'Erro: ferramenta desconhecida "{nome}".'
        try:
            return acoes[nome](**argumentos)
        except TypeError:
            return f'Erro: argumentos inválidos para "{nome}": {argumentos}.'
        except PlaywrightTimeoutError:
            return f'Erro: nenhum elemento respondeu a tempo; a referência pode não existir mais.\n\n{self.ler_pagina()}'
        except PlaywrightError as erro:
            # a primeira linha basta; o resto é o log interno do Playwright
            return f'Erro: {str(erro).splitlines()[0]}\n\n{self.ler_pagina()}'

    def ler_pagina(self):
        self.page.wait_for_load_state()
        snapshot = self.page.locator('body').aria_snapshot(mode='ai')
        if len(snapshot) > LIMITE_SNAPSHOT:
            snapshot = snapshot[:LIMITE_SNAPSHOT] + '\n[... página truncada]'
        texto = f'URL: {self.page.url}\nTítulo: {self.page.title()}\n'
        if self.dialogos:
            texto += f'Diálogo de confirmação aceito: {" | ".join(self.dialogos)}\n'
            self.dialogos.clear()
        avisos = self.page.evaluate(LER_AVISOS_JS)
        if avisos:
            texto += f'Avisos do navegador (envio bloqueado): {" | ".join(avisos)}\n'
        return f'{texto}\n{snapshot}'

    def navegar(self, caminho):
        url = urljoin(self.base_url, caminho)
        if urlsplit(url).netloc != urlsplit(self.base_url).netloc:
            return 'Erro: só é permitido navegar dentro do site em teste.'
        self.page.goto(url)
        return self.ler_pagina()

    def clicar(self, ref):
        self.page.locator(f'aria-ref={ref}').click()
        return self.ler_pagina()

    def preencher(self, ref, valor):
        self.page.locator(f'aria-ref={ref}').fill(valor)
        return self.ler_pagina()

    def voltar(self):
        self.page.go_back()
        return self.ler_pagina()
