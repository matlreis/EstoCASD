# 02 — Refatoração da base e autenticação

Commits `073aa0a` a `91fdb79`. Esta etapa reestrutura a base criada em
[01 — Bootstrap do projeto e CRUD básico](01_bootstrap_crud.md) e completa a
autenticação, registrando as decisões tomadas e as regras de negócio que
passaram a valer.

## Arquitetura ao fim da etapa

Monólito Django (MVC), com a regra de negócio concentrada em *services*. As
views só validam o formulário, chamam o service, exibem a mensagem e
redirecionam.

| App | Responsabilidade |
|---|---|
| `core/` | Código compartilhado: model abstrato `LogEvento` e helper `get_client_ip`. Não é um app registrado (não precisa estar em `INSTALLED_APPS`). |
| `estoque/` | Itens, moradores, transações (empréstimo/uso) e seus logs. `EstoqueService`. |
| `autenticacao/` | Usuário customizado `Admin`, `LogAdmin`, login/logout/cadastro, `AutenticacaoService`, signals e middleware. |
| `notificacao/` | Consulta de transações atrasadas e o comando `verificar_atrasos`. |

Templates globais ficam em `templates/` (`base.html`) e arquivos estáticos em
`static/` (`css/base.css`, `js/confirmar.js`). Cada app mantém os próprios
templates em `<app>/templates/<app>/`.

## Linha do tempo

### 1. Modelagem (`073aa0a` → `c016276`)

- **Models abstratos:**
  - `Transacao` reúne os campos comuns a `Emprestimo` e `Uso`: item, status,
    prazo e quantidade.
  - `LogEvento` reúne os campos comuns a todos os logs: IP, data e tipo do
    evento. Ele foi movido para `core/models.py` em `96e8239`.
- **FKs com `db_column`:** nomes como `id_item` geram a coluna `id_item` no
  banco, igual ao DER, em vez de `id_item_id`.
- **`on_delete=PROTECT` nas transações:** apagar um item, morador ou admin com
  histórico é bloqueado no banco. Os logs de transação (`LogUso` e
  `LogEmprestimo`) continuam com `CASCADE`.
- **`Transacao.status`** substitui o `is_active` da etapa 01. Os valores são `ATIVO`,
  `DEVOLUCAO_SINALIZADA` e `DEVOLVIDO`, e o estado intermediário permite que o
  morador sinalize a devolução antes de o admin confirmar.
- **`Item.is_active`:** permite remover um item com *soft delete* sem perder o
  histórico.
- **`Item.quant_disponivel`** é uma property: `quant_total - quant_uso`.
- **`LogEvento.ip_aparelho`** passou a ser `null=True`, porque há logs criados
  fora de um request (shell, testes, comandos).
- **Atrasos:** `Transacao.objects.atrasados()` (`TransacaoQuerySet`) substituiu
  a property `atrasado`. Assim o atraso é filtrado no banco, não em Python.

### 2. Reorganização em apps (`5ec7c92` → `44da4d7`)

- O app `database` foi renomeado para `estoque` e as migrações foram refeitas
  do zero. Por isso, **bancos locais antigos precisam ser recriados**.
- O app de autenticação, removido em `a778b2d`, foi restaurado e renomeado
  para `autenticacao`. Os
  models `Admin` e `LogAdmin` saíram do estoque e foram para ele.
- As funções de notificação foram para o novo app `notificacao`.

### 3. Views, URLs e templates (`5d5eb1c`, `5c7ca6b`, `d53cdc4`)

- A view única `gerenciar_estoque`, que despachava pelo campo `acao`, foi
  separada em
  `item_list`, `item_create`, `item_update`, `item_delete` e
  `emprestimo_create` (`estoque/urls.py`, `app_name='estoque'`).
- Os forms ficaram assim:
  - `ItemForm` é o único form de item, porque `UpdateItem` era idêntico.
  - `EmprestimoForm` reúne os dados do morador, a quantidade e o prazo.
- O `base.html` tem bloco de mensagens e cabeçalho. A confirmação de remoção é
  feita em JavaScript, pelo atributo `data-confirm`.
- `EstoqueService` (`estoque/services.py`):
  - `update_item` usa `select_for_update` e rejeita `quant_total < quant_uso`.
  - `delete_item` faz *soft delete* (`is_active=False`) e é bloqueado se houver
    transação não devolvida.

### 4. Autenticação (`f3b4515` → `91fdb79`)

- **Logout** (`f3b4515`):
  - Usa o `LogoutView` do Django, que só aceita POST desde o Django 5.0. Por
    isso o botão "Sair" do cabeçalho é um `<form method="post">`.
  - A rota é marcada com `login_not_required`. Assim, um logout sem sessão
    ativa só redireciona e não cai em loop de login.
- **`AutenticacaoService`** (`421cab4`):
  - `cadastrar(nome, email, senha)` é atômico.
  - `autenticar(email, senha)` lança `ValidationError('Email ou senha
    incorretos.')`.
  - A view de login apenas trata essa exceção.
- **Redirecionamento após o login:** o parâmetro `?next=` é respeitado
  somente se `url_has_allowed_host_and_scheme` aprovar, o que evita *open
  redirect*. Caso contrário, o usuário vai para `LOGIN_REDIRECT_URL`.
- **Validação de senha:** o `SignUpForm.clean()` roda os
  `AUTH_PASSWORD_VALIDATORS` com uma instância temporária de `Admin`, para o
  validador de similaridade comparar a senha com nome e e-mail. Com
  `LANGUAGE_CODE='pt-br'`, as mensagens saem em português.
- **Logs automáticos** (`autenticacao/signals.py`, registrados em
  `AutenticacaoConfig.ready()`):
  - Os eventos registrados são `LOGIN`, `LOGOUT` e `CONTA_CRIADA`.
  - `CONTA_CRIADA` usa `post_save` com `created and not raw`, portanto
    fixtures carregadas com `loaddata` não geram log.
  - **O IP no `post_save`:** o signal não recebe o request.
    `RequestAtualMiddleware` (`autenticacao/middleware.py`) guarda o request em
    um `ContextVar` durante cada requisição, e o signal o lê com
    `get_request_atual()`. Fora de um request, o IP fica `None`.
  - `get_client_ip` (`core/utils.py`) dá preferência a `X-Forwarded-For`,
    porque atrás do proxy do Render o `REMOTE_ADDR` é o IP do proxy.
- **Permissões** (`7e330e0`): ver regras abaixo.
- **Painel `/admin/`** (`91fdb79`): ver regras abaixo.

## Regras de negócio ao fim da etapa

### Perfis de usuário
O relatório define dois perfis, e o sistema os trata como **autenticado ×
anônimo**, sem grupos nem papéis:

- **Administrador**: membro ou funcionário do CASD. Tem conta e faz login.
- **Usuário comum**: aluno ou morador. Não tem conta e não faz login.

### Acesso às páginas
- O `LoginRequiredMiddleware` (Django 5.1+) faz **toda view exigir login por
  padrão**. Uma view pública precisa ser marcada com `@login_not_required`.
  Toda view nova nasce protegida.
- As views públicas atuais são `item_list`, `emprestimo_create`, `fazer_login`
  e `logout`.
- Um anônimo que tenta acessar uma URL protegida é redirecionado para
  `/login/?next=<url>`.

### Estoque
- O **usuário comum vê só os itens do estoque `CASD`**. O admin vê também os
  da `ZELADORIA`.
- Os botões "Adicionar", "Editar" e "Remover" só aparecem para o admin. As
  próprias rotas também são protegidas, então não basta esconder o botão.
- "Emprestar" aparece só para itens `CASD`. **Empréstimo** é sempre de um item
  `CASD` para um morador. **Uso** é de um item da `ZELADORIA` por um admin.
- `quant_total` não pode ficar menor que `quant_uso`.
- Um item com transação não devolvida não pode ser removido. A remoção é
  sempre *soft delete*.
- Um registro com histórico nunca é apagado do banco (`PROTECT`).

### Contas de administrador
- **Todo admin cadastra outro admin** pela página `/cadastro/`. O link fica no
  cabeçalho e só é visível para quem está logado.
- No painel `/admin/`, o checkbox **"Gestor"** (`is_superuser`) é a única
  permissão visível. Ao salvar, `is_staff` recebe o mesmo valor
  (`AdminAdmin.save_model`), então quem é gestor também entra no painel.
  - **Admin comum** usa só as telas do sistema.
  - **Gestor** também acessa o `/admin/` para gerenciar contas e consultar
    logs.
- **Contas não são excluídas.** A conta é desativada desmarcando "Ativo"
  (`has_delete_permission=False`).
- **Os logs são somente leitura** no painel: não há como adicionar, editar ou
  excluir.
- O primeiro gestor é criado com `uv run manage.py createsuperuser`.

## Configuração relevante (`estoque_casd/settings.py`)

- `AUTH_USER_MODEL = 'autenticacao.Admin'`. O login é feito por e-mail
  (`USERNAME_FIELD='email'`).
- `LOGIN_URL = 'autenticacao:login'`. `LOGIN_REDIRECT_URL` e
  `LOGOUT_REDIRECT_URL` apontam para `estoque:item_list`.
- No `MIDDLEWARE`, a ordem importa:
  - `LoginRequiredMiddleware` vem depois de `AuthenticationMiddleware`.
  - `RequestAtualMiddleware` fica por último.
- `LANGUAGE_CODE = 'pt-br'` e `TIME_ZONE = 'America/Sao_Paulo'`.

## Próximos passos (a partir desta etapa)

1. **Testes da autenticação:**
   - logout por GET retorna 405;
   - `next` externo é ignorado;
   - views protegidas redirecionam o anônimo;
   - anônimo não vê itens da `ZELADORIA`;
   - signals gravam o IP.
2. **`TransacaoService` e a view `emprestimo_create`**, que hoje é um
   placeholder:
   - validar que o item é `CASD` e que `quant <= quant_disponivel`;
   - fazer `get_or_create` do morador por e-mail;
   - incrementar `quant_uso` com `select_for_update` e `F()`;
   - criar o `LogEmprestimo`;
   - a view é pública, portanto toda validação deve ficar no service.
3. **Devolução:** o morador sinaliza (`DEVOLUCAO_SINALIZADA`) e o admin
   confirma (`DEVOLVIDO`), o que decrementa `quant_uso`. Depois vem o fluxo de
   uso para itens da `ZELADORIA`.
4. **Melhorias nos models do estoque:**
   - registrar os models no `estoque/admin.py`;
   - adicionar `__str__` e `verbose_name`;
   - definir rótulos para os `TextChoices`.
5. **Notificações por e-mail** de atraso, a partir de `verificar_atrasos`.
