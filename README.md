# EstoCASD
Sistema para controle de estoque do Centro Acadêmico Santos Dumont (CASD).

# Requisitos

Esse projeto requer Python 3.14, gerenciador de pacotes uv e PostgreSQL 18.6. 

# Configuração de desenvolvimento

Clone o repositório em um diretório. Execute `uv sync` na pasta raiz do projeto 
para instalar as dependências. Para auxiliar a configuração, copie o 
arquivo `.env.example`, renomeie a cópia para `.env` e o modifique conforme as 
instruções a seguir. 

## Django

Execute o comando `uv run python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'` 
para gerar a secret-key  do Django e a insira no arquivo `.env` no seguinte 
formato:

    DJANGO_SECRET_KEY="your-django-secret-key"

## PostgreSQL

Crie um novo usuário e um banco de dados controlado pelo novo usuário, 
definindo a sua senha. Certifique-se que o usuário tenha permissão de leitura e
escrita de bancos de dados (`CREATEDB` role). No arquivo `.env`, crie as 
seguintes variáveis:

    DB_NAME=DBNAME
    DB_USER=USER
    DB_PASSWORD="PASSWORD"

Os placeholders `DBNAME`, `USER` e `PASSWORD` referem-se, respectivamente, ao 
nome do banco de dados, ao nome do usuário e à senha do usuário escolhida.

# Acessar servidor

Rode o comando `uv run manage.py check` para verificar se o ambiente foi 
corretamente configurado.

Para acessar o servidor no localhost, realize as migrações com e 
`uv run manage.py migrate` e então execute `uv run manage.py runserver` para 
rodar o servidor de desenvolvimento na porta 8000.

> Nota: algumas migrações requerem que o banco de dados local seja recriado do 
zero.

## Primeiro superusuário

No estado atual do projeto, o primeiro superusuário deve ser criado a partir da
linha de comando. Execute `uv run manage.py createsuperuser` para criá-lo. A
partir dele, outros administradores podem ser criados a partir da interface do
site.

# Testes

Execute o comando `uv run manage.py test` para rodar a bateria de testes, que
pode ser consultada nos arquivos `tests.py` em cada aplicativo (`autenticacao`, 
`estoque`, `notificacao` e `core`). É possível, também, realizar os testes de 
um aplicativo específico com `uv run manage.py test app`, em que `app` deve ser
substituido por um dos aplicativos do sistema.

## Teste cego por LLM

Em `tests_llm`, um modelo de linguagem usa o site pelo navegador como um 
cliente, sem conhecer o código-fonte, e relata o que encontrar. Esse teste não
faz parte da suíte de testes normal e é ignorado por padrão.

Execute `uv run playwright install chromium` para instalar o navegador. No 
arquivo `.env`, defina o provedor e o modelo, que deve suportar *tool calling*.
Qualquer API compatível com a da OpenAI serve (OpenRouter, Ollama, Gemini...):

    LLM_BASE_URL=https://openrouter.ai/api/v1
    LLM_API_KEY="your-api-key"
    LLM_MODEL=provider/model-name:free

Rode `RUN_LLM_TEST=1 uv run manage.py test tests_llm` para executar todas as 
ações, ou `RUN_LLM_TEST=1 uv run manage.py test tests_llm.tests.TesteCegoLLM.test_...` 
para executar uma em específico. O `test_ferramentas` valida o navegador sem 
chamar o modelo. Defina `LLM_HEADED=1` para acompanhar a janela do navegador com
as ações do modelo e `LLM_SLOW_MO=1` para desacelerá-las.

Os achados são gravados em `tests_llm/reports/` e não reprovam o teste, pois a
saída do modelo não é determinística: o teste só falha se o agente não concluir
a ação no número definido de passos. Bugs verificados devem virar testes 
determinísticos com `@expectedFailure`.

> Nota: planos gratuitos limitam as requisições por minuto e por dia, e cada 
ação gasta até 30 requisições. Esses provedores podem registrar os prompts, 
então use apenas dados fictícios.
