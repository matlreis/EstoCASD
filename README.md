# Estoque-CASD
Sistema para controle de estoque do Centro Acadêmico Santos Dumont (CASD).

# Requisitos

Esse projeto requer Python 3.14, gerenciador de pacotes uv e PostgreSQL 18.6. 

# Configuração

Clone o repositório em um diretório. Execute `uv sync` na pasta raiz do projeto 
para instalar as dependências. 

## Django

Execute o comando `uv run python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'` para gerar a secret-key do Django e a insira no arquivo `.env` no seguinte formato:

    DJANGO_SECRET_KEY="your-django-secret-key"

## PostgreSQL

Crie um novo usuário e um banco de dados controlado pelo novo usuário. No 
diretório raiz do projeto, crie os arquivos `.pg_service.conf` e`.my_pgpass` e 
nos respectivos formatos:

`.pg_service.conf`:

    localhost:5432:DBNAME:USER:YOUR_PASSWORD

`.my_pgpass`:

    [my_service]
    host=localhost
    user=USER
    dbname=DBNAME
    port=5432

Os placeholders `DBNAME`, `USER` e `YOUR_PASSWORD ` referem-se 
ao nome do banco de dados criado, ao nome do usuário e à sua senha, respectivamente.

# Acessar servidor

Para acessar o servidor no localhost, realize as migrações com `uv run manage.py makemigrations` e `uv run manage.py migrate` e então execute `uv run manage.p runserver` para rodar o servidor de desenvolvimento na porta 8000.