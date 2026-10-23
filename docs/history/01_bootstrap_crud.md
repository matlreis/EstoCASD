# 01 — Bootstrap do projeto e CRUD básico

Commits `5de9351` a `a778b2d`. Esta etapa vai da criação do repositório até o
primeiro CRUD de itens e os esboços de autenticação e empréstimo.

> Boa parte do que está descrito aqui foi substituída na etapa 02. O objetivo
> deste arquivo é explicar a origem das decisões que permaneceram.

## Linha do tempo

### 1. Ambiente (`5de9351` → `3458208`)

- Projeto gerenciado com **uv**, Python **3.14** e Django **6.1**.
- O pacote Django é `estoque_casd/`, na raiz. O layout `src/` criado pelo
  `uv init` foi descartado, assim como o `[build-system]`, porque o projeto é
  uma aplicação e não uma biblioteca.
- `python-dotenv` lê os segredos do `.env`. O app de exemplo `polls`, do
  tutorial do Django, foi removido.

### 2. Banco de dados e modelagem inicial (`366a8fa`, `a1a56cd`)

- O banco passou de **SQLite para PostgreSQL** (driver `psycopg` 3).
- Os models seguem o DER do relatório e ficaram em um único app, `database`:
  `Admin`, `LogAdmin`, `Item`, `Uso`, `LogUso`, `Morador`, `Emprestimo` e
  `LogEmprestimo`.
- **Decisões que continuam valendo:**
  - **`Admin` é o usuário do sistema.** Ele estende `AbstractBaseUser` e
    `PermissionsMixin` e está definido em `AUTH_USER_MODEL`. O login é feito
    por **e-mail** (`USERNAME_FIELD='email'`), e o hash e o salt da senha ficam
    a cargo do Django (`set_password`). A tabela se chama `admin`
    (`db_table`), como no DER.
  - **Tipos de estoque:** `Item.TipoEstoque` tem os valores `CASD` e
    `ZELADORIA`. A disponibilidade é calculada a partir de `quant_total` e
    `quant_uso`.
  - **Morador sem conta:** `Morador` é identificado pelo e-mail
    (`unique=True`), que também será usado para notificações.
- **Ajustes do `a1a56cd`:**
  - O campo `nome_user` foi removido do `Admin`. Basta e-mail e nome.
  - Os nomes dos models foram padronizados em CamelCase (`LogAdmin` etc.) e os
    campos em inglês (`limit_date`, `event_date`).
  - `ip_aparelho` passou a ser `GenericIPAddressField`, que aceita IPv4 e
    IPv6.
  - `quant` foi adicionado às transações, e `email` ao `Morador`.

### 3. Atrasos (`1b75b48`, `9eaa436`)

- `database/services.py` ganhou `emprestimos_atrasados()` e `usos_atrasados()`.
  Elas retornam as transações ativas com prazo vencido e usam
  `select_related` para evitar consultas N+1.
- O comando `uv run manage.py verificar_atrasos` lista os atrasos no
  terminal. É a base das futuras notificações por e-mail.
- Os primeiros testes cobrem essas funções e estão hoje em
  `notificacao/tests.py`.

### 4. Configuração por variáveis de ambiente (`6bb6805`, `8d06d26`)

- A conexão com o banco deixou de usar `.pg_service.conf` e `.my_pgpass` e
  passou a ler `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` e `DB_PORT` do
  ambiente. Isso prepara o deploy, já que o Render e o Supabase/Neon fornecem
  credenciais por variável.
- O `.env.example` e o README documentam a configuração local.

### 5. CRUD de itens e esboços (`7e9bf34`, `a05dae0`, `014ee20`)

- **CRUD de itens:**
  - Uma view única, `gerenciar_estoque`, na rota `/`, com o template
    `estoque.html`.
  - A ação do POST é escolhida pelo campo `acao`: `criar`, `atualizar`,
    `deletar` ou `emprestar`.
  - O create usa um `ModelForm` (`ItemForm`, depois dividido em `CreateItem` e
    `UpdateItem`). O update grava os valores do POST direto, sem validação.
    O delete apaga a linha de fato.
  - O cadastro de item só pede `nome`, `tipo_estoque` e `quant_total`.
    `quant_uso` começa em 0 e não é editável pelo usuário.
- **Esboço da autenticação:** o app `authentification` tem login, cadastro e
  signals de `LOGIN` e `LOGOUT` em `LogAdmin`, que gravam o `REMOTE_ADDR`.
- **Esboço do empréstimo:** a view `pegar_emprestimo` só salvava o `Morador`,
  ainda sem a transação.
- O commit `a778b2d` removeu o app `authentification` junto com o ajuste de
  configuração. Ele foi restaurado na etapa 02 (`8521ba3`).

## Estado ao fim da etapa

Problemas conhecidos e como a etapa 02 os resolveu:

| Problema | Solução na etapa 02 |
|---|---|
| Uma view para todas as ações, sem validação no update | Uma view por ação, com `EstoqueService` |
| `redirect('')`, rota com nome vazio | Namespaces `estoque:` e `autenticacao:` |
| `CASCADE` apagava o histórico de transações | `PROTECT`, e *soft delete* de item |
| `is_active` não representava a devolução sinalizada | `Transacao.status` com três estados |
| Signals sem registro confiável e IP obrigatório | Signals em `autenticacao`, IP opcional, `get_client_ip` |
| Sem nenhuma restrição de acesso | `LoginRequiredMiddleware` e regras por perfil |
