# Estoque-CASD
Sistema para controle de estoque do Centro Acadêmico Santos Dumont (CASD).

# Requisitos

Esse projeto requer Python 3.14, gerenciador de pacotes uv e PostgreSQL 18.6. 

# Configuração de desenvolvimento

Clone o repositório em um diretório. Execute `uv sync` na pasta raiz do projeto 
para instalar as dependências. Para auxiliar a configuração, copie o 
arquivo `.env.example`, renomeie a cópia para `.env` e o modifique conforme as 
instruções a seguir. 

## Django

Execute o comando `uv run python -c 'from django.core.management.utils import 
get_random_secret_key; print(get_random_secret_key())'` para gerar a secret-key 
do Django e a insira no arquivo `.env` no seguinte formato:

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

Para acessar o servidor no localhost, realize as migrações com `uv run
manage.py makemigrations` e `uv run manage.py migrate` e então execute
`uv run manage.py runserver` para rodar o servidor de desenvolvimento na porta 
8000.

# Testes

Execute o comando `uv run manage.py test` para rodar a bateria de testes, que
pode ser consultada no arquivo `database/tests.py`.
