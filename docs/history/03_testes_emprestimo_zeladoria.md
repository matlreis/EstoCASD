# 03 — Testes, empréstimos e zeladoria

Commits `78131ad` a `2709a66`. Esta etapa parte de
[02 — Refatoração da base e autenticação](02_refatoracao_autenticacao.md).
Nela, o **`Uso` foi descartado** e o `Item` foi dividido em dois estoques
independentes. A etapa também cria a bateria de testes, implementa o fluxo
completo de empréstimo e devolução e o CRUD da zeladoria com histórico.

> Os próximos passos 2 a 4 da etapa 02 foram feitos com mudanças, descritas
> abaixo. O passo 3 previa um fluxo de uso para a zeladoria, que **não será
> mais implementado**. As decisões vêm das reuniões com o CASD, registradas em
> [`docs/minutes/`](../minutes/).

## Arquitetura ao fim da etapa

Os apps continuam os mesmos da etapa 02. O que mudou:

| App | Mudança |
|---|---|
| `estoque/` | `Item` virou abstrato e deu origem a `ItemCASD` e `ItemZeladoria`. `Uso`, `LogUso` e `Transacao` foram removidos. `services.py` tem três classes: `EstoqueService` (itens do CASD), `EmprestimoService` e `ZeladoriaService`. |
| `notificacao/` | Trata só de empréstimos atrasados. |
| `core/` | `get_client_ip` passou a validar o IP. |

O pacote Django continua sendo `estoque_casd/`. Só o nome do projeto mudou
(ver item 1).

## Linha do tempo

### 1. Documentação e nome do projeto (`78131ad` → `003b07c`)

- `docs/` foi criada com três subpastas:
  - `labs/`: entregas da disciplina.
  - `history/`: este histórico.
  - `minutes/`: atas das reuniões com o CASD.
- O projeto passou a se chamar **EstoCASD** (`899c91b`). A mudança vale para o
  `name` do `pyproject.toml`, para os títulos dos templates e para os nomes
  sugeridos no `.env.example` (`estocasd_db`, `estocasd`).

### 2. Remoção do `Uso` e divisão do `Item` (`05a6742`)

Na reunião 01, o CASD informou que os itens da zeladoria não são emprestados
entre membros. Para eles, bastam a quantidade e o histórico. Com isso:

- **`Uso`, `LogUso` e o abstrato `Transacao` foram removidos.** O status, o
  prazo, a quantidade e o QuerySet passaram direto para `Emprestimo`, com
  `EmprestimoQuerySet`:
  - `ativos()` retorna os empréstimos não devolvidos.
  - `atrasados()` retorna os `ATIVO` com `limit_date < timezone.localdate()`.
- **`Item` virou abstrato** (`nome`, `quant_total`, `is_active`, `__str__`) e
  deu origem a dois models com **tabelas separadas**. `tipo_estoque` deixou de
  existir.
  - `ItemCASD` tem `quant_emprestada` e a property `quant_disponivel`.
    `quant_emprestada` substitui o antigo `quant_uso`.
  - `ItemZeladoria` tem `preco_unitario` (opcional, só para itens vendidos).
- **`LogItemZeladoria`** guarda o histórico da zeladoria: admin,
  `quant_anterior`/`quant_nova` e o evento.
- **`Emprestimo.limit_date`** passou de `DateTimeField` para `DateField`. Prazo
  é contado em dias, e o atraso também (`verificar_atrasos` imprime "Nd de
  atraso").
- Os models do estoque ganharam `__str__`, `verbose_name` e rótulos nos
  `TextChoices`. Isso cumpre parte do passo 4 da etapa 02.
- A migração `0002` apaga a tabela `Item` e não copia os dados para as novas
  tabelas. **Bancos locais com dados precisam ser recriados.**

### 3. Bateria de testes (`18ee2f8` → `95d51e1`)

- Cada app tem um `tests.py`. A suíte roda com `uv run manage.py test` (ver o
  README).
- Os testes da autenticação cobrem os itens do passo 1 da etapa 02, mais as
  regras do painel `/admin/`, CSRF, middleware e signals. Os testes da
  `notificacao` cobrem a saída de `verificar_atrasos`.
- **Convenções:**
  - Testes com senha usam `@SENHA_RAPIDA` (hasher MD5), para acelerar a suíte.
  - Testes com datas usam `@FIXAR_HOJE` (`estoque/tests.py`), que fixa
    `timezone.localdate()` em uma quinta-feira. Assim, nenhum teste depende do
    dia em que roda.
  - **Bugs conhecidos** são documentados por um teste do comportamento correto
    marcado com `@expectedFailure` (`036d761`). Quando o bug é corrigido, o
    teste passa a dar *unexpected success*, e basta remover o decorador.
- Os testes de `X-Forwarded-For` inválido só falhavam no PostgreSQL, porque o
  SQLite aceita qualquer texto no campo de IP. **Rode a suíte no PostgreSQL.**

### 4. Correções da autenticação (`8cf8827`, `17537e5`, `ff9ecee`)

As correções resolveram os três bugs documentados no item anterior. Os
decoradores `@expectedFailure` foram removidos, e os testes agora protegem
contra regressões.

- **`get_client_ip`** ignora valores inválidos. Ele valida o IP com
  `ipaddress` e, se o `X-Forwarded-For` for inválido, tenta o `REMOTE_ADDR`.
  Se nenhum for válido, devolve `None`. Antes, um cabeçalho como `unknown`
  causava erro 500 ao gravar o log.
- **E-mail sem diferenciar maiúsculas:**
  - `AdminManager.get_by_natural_key` busca com `__iexact`, então o login
    aceita `A@TEST.com`.
  - `Admin.validate_unique` recusa um e-mail repetido com outra caixa. Antes,
    o cadastro dava `IntegrityError`.
- **Senhas não são mais "aparadas"** (`strip=False`). Uma senha com espaço no
  fim, criada pelo painel, não conseguia fazer login pelo formulário.

### 5. Empréstimo e devolução (`60d4c99` → `16364d2`)

- **`LogEmprestimo`** ganhou eventos (`CRIADO`, `DEVOLUCAO_SINALIZADA` e
  `DEVOLUCAO_CONFIRMADA`) e `id_admin`, que é nulo nas ações do morador.
- **`EmprestimoService.criar_emprestimo(item, dados, ip)`** é atômico e trava
  o item com `select_for_update`. Toda a validação fica aqui, porque a view é
  pública:
  - o item precisa estar ativo;
  - a quantidade deve satisfazer `1 <= quant <= quant_disponivel`;
  - `limit_date` não pode estar no passado nem passar de `PRAZO_MAX_DIAS`
    (60), e não pode cair em sábado ou domingo, porque não há expediente
    (reunião 01).
  - O morador é encontrado pelo e-mail em minúsculas
    (`update_or_create`), e **nome e ap são atualizados** com os dados mais
    recentes.
  - O service incrementa `quant_emprestada` e cria o `LogEmprestimo`.
- O `EmprestimoForm` repete o prazo nos atributos `min` e `max` do campo de
  data, só para ajudar no navegador. A regra continua no service.
- **Devolução em duas etapas** (reunião 01: a devolução só vale com a
  confirmação de um admin):
  - `sinalizar_devolucao(item, email, ip)`: na view pública
    `devolucao_sinalizar` (`itens/<pk>/devolver/`), o morador informa o
    e-mail. Todos os empréstimos `ATIVO` dele naquele item para aquele e-mail
    passam a `DEVOLUCAO_SINALIZADA`, com um log para cada um. `quant_emprestada`
    não muda.
  - `confirmar_devolucao(emprestimo, admin, ip)`: na lista `emprestimos/`
    (`emprestimo_list`, só para admin), o admin confirma. O empréstimo vai para
    `DEVOLVIDO` e `quant_emprestada` é decrementada. **O admin também pode
    confirmar um empréstimo `ATIVO` sem sinalização**, mas não pode confirmar
    duas vezes.
  - `listar_ativos()` traz os empréstimos ativos e os sinalizados, ordenados
    pelo prazo.

### 6. Zeladoria (`40e3580` → `2709a66`)

- `preco_unitario` tem restrição de ser positivo pelo Model.
- **`ZeladoriaService`** recebe sempre o `admin` e o `ip`, porque toda ação
  gera um `LogItemZeladoria`:
  - `create_item` registra o evento `CRIADO`, com `quant_nova`.
  - `update_item` registra `QUANTIDADE_ALTERADA` **somente se `quant_total`
    mudar**. Alterar só o nome ou o preço não entra no histórico.
  - `delete_item` faz *soft delete* e registra `REMOVIDO`. Ele não tem
    bloqueio, porque a zeladoria não tem empréstimos.
  - `historico(item)` retorna os logs do item, do mais recente para o mais
    antigo. **Ainda não há view para ele.**
- **Views** `zeladoria_list`, `zeladoria_create`, `zeladoria_update` e
  `zeladoria_delete`, em `zeladoria/...`. **Todas exigem login.** O usuário
  comum não vê a zeladoria.
- O cabeçalho do admin ganhou os links "Empréstimos" e "Zeladoria".
- **A coluna "em uso" foi criada e removida.** `05a6742` criou
  `ItemZeladoria.quant_uso`, o evento `USO_ALTERADO` e a property `em_uso`, 
  mantido provisoriamente após a reunião 1. A reunião 02 concretizou a remoção
  da coluna, feita em `76ff9e1` (migração `0005`).

## Regras de negócio ao fim da etapa

As regras da etapa 02 sobre perfis, contas e painel continuam valendo. As
regras de estoque passam a ser estas:

### Acesso às páginas
- Views públicas:
  - `item_list`;
  - `emprestimo_create`;
  - `devolucao_sinalizar`;
  - `fazer_login`;
  - `logout`.
- Todo o resto exige login, inclusive `emprestimo_list`,
  `devolucao_confirmar` e as views da zeladoria.

### Estoque do CASD
- A página inicial lista só `ItemCASD`. Qualquer pessoa pode **Emprestar** e
  **Devolver**. Somente o admin pode **Adicionar**, **Editar** e **Remover**.
- `quant_total` não pode ficar menor que `quant_emprestada`.
- Um item com empréstimo ativo ou com devolução sinalizada não pode ser
  removido. A remoção é sempre *soft delete*.
- As operações do `EstoqueService` (CASD) **não geram log**. Só os
  empréstimos têm histórico.

### Empréstimos
- O morador não tem conta e é identificado pelo **e-mail**, sem diferenciar
  maiúsculas.
- O prazo vai de hoje até 60 dias e precisa cair em dia útil.
- O ciclo é `ATIVO` → `DEVOLUCAO_SINALIZADA` → `DEVOLVIDO`. A sinalização é
  opcional, mas só o admin devolve a quantidade ao estoque.
- "Atrasado" significa um empréstimo `ATIVO` com prazo vencido. Um empréstimo
  com devolução sinalizada não conta como atraso.

### Zeladoria
- A zeladoria é só para o admin e não tem empréstimo nem uso. O sistema
  guarda o nome, a quantidade e o preço opcional, e registra um histórico de
  criação, alteração de quantidade e remoção.

## Próximos passos (a partir desta etapa)

A maioria vem da [reunião 02](../minutes/02.md).

1. **Formulário de empréstimo:**
   - adicionar o telefone;
   - trocar "nome" por "nome/apelido" (ex.: Matheus/General).

   Isso muda `Morador`, `EmprestimoForm` e os testes.
2. **Atalho para iniciativas** (CASD Curso, Atlética etc.): em vez de nome, ap
   e e-mail, pedir o nome da iniciativa e do representante.
   - Iniciativas **não recebem notificações por e-mail**.
   - É preciso decidir como modelar isso, porque hoje o `Morador` exige um
     e-mail único. Uma opção é um model `Iniciativa` com uma FK opcional no
     `Emprestimo`.
3. **Agendamento de empréstimos:** permitir que o empréstimo comece em uma
   data futura, contornando a falta de expediente no fim de semana.
   - Isso provavelmente exige um status novo (ex.: `AGENDADO`) e uma regra
     de reserva de quantidade.
4. **Vendas na zeladoria:**
   - um botão na lista leva a um formulário com comprador, ap, vaga e
     quantidade vendida.
   - as vendas formam um histórico (`Venda`).
   - Vendas decrementam a quantidade total do item; deve-se adicionar um novo 
     log (ex.: `VENDA`) em `LogItemZeladoria`.
     
5. **Histórico e dashboard:**
   - uma página de histórico de empréstimos (os `DEVOLVIDO` não aparecem em
     nenhuma tela hoje);
   - uma view para `ZeladoriaService.historico`;
   - um dashboard com os itens mais vendidos, as iniciativas que mais usam e
     as que mais atrasam, dentre outras informações.
6. **Notificações de atraso por e-mail** para moradores, a partir de
   `verificar_atrasos`.
7. **Pendências da etapa 02:**
   - registrar os models do estoque no `estoque/admin.py` (somente leitura
     para logs, como em `autenticacao`);
   - definir `verbose_name` em `LogEmprestimo`.
8. **Identidade visual** pelo Canva do CASD e **QR Code por item** (reunião 01).
