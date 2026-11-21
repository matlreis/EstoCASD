"""
Ações do teste cego por LLM: o que o cliente sabe sobre o CASD e o que ele quer fazer no site.
Os textos descrevem objetivos e regras como o CASD os conhece, nunca detalhes de implementação.
Todos os dados são fictícios, porque os prompts são enviados a um provedor externo.
"""

from estoque.services import ANTECEDENCIA_MAX_DIAS_UTEIS, PRAZO_MAX_DIAS_UTEIS


# conta semeada pelo tests.py e usada nas ações de administrador
EMAIL_ADMIN = 'gestor@casd.test'
SENHA_ADMIN = 'Gestor-Casd-4821'

# Regras do CASD conhecidas pelo cliente (atas e documento de requisitos).
# Fornecem as regras de negócio do sistema para que o modelo possa sinalizar
# descumprimentos às regras.
CONTEXTO_CLIENTE = f"""\
- Qualquer pessoa pode ver os itens do CASD disponíveis, pegar um item emprestado e avisar que o \
devolveu, sem precisar de conta.
- Para pegar um empréstimo, o morador informa nome, apartamento e e-mail. O e-mail identifica a \
pessoa, sem diferenciar maiúsculas de minúsculas.
- A quantidade emprestada é de pelo menos 1 e no máximo a quantidade disponível do item.
- O morador informa quando vai retirar o item (a retirada pode ser agendada) e quando vai devolver. \
Como o CASD não abre no fim de semana, as duas datas precisam cair em dia útil. A retirada pode ser \
hoje ou até {ANTECEDENCIA_MAX_DIAS_UTEIS} dias úteis à frente, e a devolução não pode ser antes da \
retirada nem mais de {PRAZO_MAX_DIAS_UTEIS} dias úteis depois dela. Um agendamento já reserva a \
quantidade, que deixa de estar disponível para outros.
- A devolução só vale quando um administrador a confirma. O morador pode avisar antes que \
devolveu, mas, até a confirmação, o item continua contando como emprestado.
- Um empréstimo está atrasado quando o prazo passou e o morador não avisou a devolução. Os \
administradores precisam saber quais empréstimos estão atrasados.
- Administradores são membros e funcionários do CASD e entram com e-mail e senha. Eles cadastram, \
editam e removem itens, acompanham os empréstimos, confirmam devoluções e cadastram outros \
administradores.
- Um item com empréstimo em andamento não pode ser removido, e a quantidade total de um item não \
pode ficar menor que a quantidade emprestada.
- A zeladoria tem um estoque interno, visível só para administradores. Cada produto tem nome, \
quantidade e, se for vendido, o preço unitário. Uma venda registra comprador, apartamento/vaga \
e quantidade, diminui o estoque e entra no histórico do produto e no registro de vendas."""

ACAO_MORADOR_EMPRESTIMO = """\
Você é Pedro, morador do apartamento 101, com o e-mail pedro@casd.test. Você quer pegar \
emprestadas 2 unidades da Escada para devolver na próxima sexta-feira. Depois de pegar, avise pelo \
site que já devolveu. Confira se a quantidade disponível mostrada pelo site faz sentido antes e \
depois de cada passo."""

ACAO_MORADOR_LIMITES = """\
Você é Ana, moradora do apartamento 202, com o e-mail ana@casd.test, e quer descobrir se o site \
aceita pedidos que não deveria. Tente, por exemplo: pegar mais unidades do que as disponíveis, \
zero ou um número negativo; marcar a devolução para um sábado, para uma data passada e para \
daqui a três meses; usar o seu e-mail com letras maiúsculas; avisar a devolução de um item que \
você não pegou; abrir, sem entrar com uma conta, páginas que deveriam ser só dos administradores."""

ACAO_ADMIN_ESTOQUE = f"""\
Você é membro do CASD e administra o estoque. Entre com o e-mail {EMAIL_ADMIN} e a senha \
{SENHA_ADMIN}. Cadastre o item "Bola de vôlei" com 4 unidades e depois corrija a quantidade para 5. \
Tente remover um item que está emprestado e tente deixar a quantidade de um item menor do que a \
emprestada. Por fim, veja os empréstimos, identifique os atrasados e confirme a devolução que um \
morador já avisou."""

ACAO_ADMIN_ZELADORIA = f"""\
Você é funcionário da zeladoria do CASD. Entre com o e-mail {EMAIL_ADMIN} e a senha {SENHA_ADMIN}. \
Cadastre o produto "Detergente" com 10 unidades a R$ 3,50 cada e registre a venda de 3 detergentes \
para Carla, apartamento 101A Vaga F. Confira se o estoque, o histórico do produto e a lista de vendas \
refletem a venda. Tente também vender mais unidades do que há e vender um produto sem preço."""

ACAO_GESTOR_CONTAS = f"""\
Você é o gestor do CASD. Entre com o e-mail {EMAIL_ADMIN} e a senha {SENHA_ADMIN}. Cadastre um novo \
administrador, Bruno, com o e-mail bruno@casd.test: tente primeiro uma senha fraca, como 12345678, \
e depois uma senha forte. Tente também cadastrar de novo o mesmo e-mail com letras maiúsculas. Saia \
da sua conta e entre com a do Bruno para conferir que ela funciona."""
