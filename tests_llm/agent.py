"""
Loop do agente do teste cego por LLM.
O modelo recebe a ação e as regras do CASD como um cliente as conhece, pede ações ao navegador
e registra os achados. O provedor e o modelo vêm do ambiente (LLM_BASE_URL, LLM_API_KEY e
LLM_MODEL), então qualquer API compatível com a da OpenAI serve (OpenRouter, Ollama etc.).
"""
import json
import os
from dataclasses import dataclass, field

from django.utils import timezone
from openai import OpenAI

from .browser import FERRAMENTAS

# limite de requisições ao modelo por ação
MAX_PASSOS = 30

DIAS_SEMANA = ['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo']

# Ferramentas que não usam o navegador
FERRAMENTAS_AGENTE = [
    {
        'type': 'function',
        'function': {
            'name': 'registrar_achado',
            'description': 'Registra um problema encontrado no site.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'gravidade': {'type': 'string', 'enum': ['baixa', 'media', 'alta']},
                    'titulo': {'type': 'string', 'description': 'Resumo do problema em uma frase'},
                    'passos': {'type': 'string', 'description': 'O que você fez até o problema aparecer'},
                    'esperado': {'type': 'string', 'description': 'O que deveria ter acontecido'},
                    'obtido': {'type': 'string', 'description': 'O que aconteceu de fato'},
                },
                'required': ['gravidade', 'titulo', 'passos', 'esperado', 'obtido'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'concluir',
            'description': 'Encerra a ação.',
            'parameters': {
                'type': 'object',
                'properties': {'resumo': {'type': 'string', 'description': 'O que você testou e o que concluiu'}},
                'required': ['resumo'],
            },
        },
    },
]

PROMPT_SISTEMA = """\
Você é um cliente testando o EstoCASD, o site de controle de estoque do Centro Acadêmico Santos \
Dumont (CASD). Você deve acessar o site pelo navegador, com as ferramentas disponíveis.

Como trabalhar:
- Leia a página antes de agir e use as referências [ref=...] da leitura mais recente; elas mudam a \
cada página.
- Cumpra a ação como um usuário real faria e tente também o que um usuário distraído ou \
mal-intencionado tentaria.
- Sempre que algo parecer errado, chame registrar_achado: erro do servidor, mensagem confusa ou \
ausente, dado incorreto, ação permitida que deveria ser proibida (ou o contrário), regra do CASD \
desrespeitada. Não registre o mesmo problema duas vezes.
- Registre apenas o que você observou na página.
- Ao terminar a ação, ou se não houver mais o que testar, chame concluir com um resumo.

Hoje é {hoje}.

O que você sabe sobre o CASD:
{contexto}"""


@dataclass
class Resultado:
    achados: list = field(default_factory=list)
    acoes: list = field(default_factory=list)  # (passo, ferramenta, argumentos) para o relatório
    resumo: str = ''
    passos: int = 0
    concluiu: bool = False


def executar_acao(navegador, acao, contexto):
    """Conduz uma ação até o modelo chamar `concluir` ou estourar MAX_PASSOS."""
    cliente = OpenAI(base_url=os.environ['LLM_BASE_URL'], api_key=os.environ['LLM_API_KEY'], max_retries=5)
    hoje = timezone.localdate()
    prompt = PROMPT_SISTEMA.format(hoje=f'{hoje:%d/%m/%Y} ({DIAS_SEMANA[hoje.weekday()]})', contexto=contexto)
    mensagens = [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': f'Ação: {acao}\n\nO navegador está na página inicial do site. Comece com ler_pagina.'},
    ]
    navegador.navegar('/')
    resultado = Resultado()
    ultima_pagina = None

    for passo in range(1, MAX_PASSOS + 1):
        resultado.passos = passo
        resposta = cliente.chat.completions.create(
            model=os.environ['LLM_MODEL'],
            messages=mensagens,
            tools=FERRAMENTAS + FERRAMENTAS_AGENTE,
        )
        mensagem = resposta.choices[0].message
        mensagens.append(mensagem.model_dump(exclude_none=True))

        if not mensagem.tool_calls:
            # alguns modelos respondem em texto em vez de chamar ferramentas
            mensagens.append({'role': 'user', 'content': 'Continue usando as ferramentas. Ao terminar, chame concluir.'})
            continue

        for chamada in mensagem.tool_calls:
            nome = chamada.function.name
            try:
                argumentos = json.loads(chamada.function.arguments or '{}')
            except json.JSONDecodeError:
                argumentos = None
            print(f'[{passo}] {nome} {argumentos}')
            resultado.acoes.append((passo, nome, argumentos))
            retorno = {'role': 'tool', 'tool_call_id': chamada.id}

            if argumentos is None:
                retorno['content'] = 'Erro: os argumentos não são um JSON válido.'
            elif nome == 'registrar_achado':
                resultado.achados.append(argumentos)
                retorno['content'] = 'Achado registrado.'
            elif nome == 'concluir':
                resultado.resumo = argumentos.get('resumo', '')
                resultado.concluiu = True
                retorno['content'] = 'Ação concluída.'
            else:
                retorno['content'] = navegador.executar(nome, argumentos)
                # só a página mais recente vai completa; das anteriores fica a primeira linha
                if ultima_pagina:
                    ultima_pagina['content'] = ultima_pagina['content'].split('\n', 1)[0] + ' [página antiga omitida]'
                ultima_pagina = retorno
            mensagens.append(retorno)

        if resultado.concluiu:
            break

    return resultado
