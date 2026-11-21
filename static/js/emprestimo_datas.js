// Ajusta as datas selecionáveis da devolução conforme a retirada escolhida:
// da própria retirada até o prazo máximo depois dela.
(function () {
    const retirada = document.getElementById('id_start_date');
    const devolucao = document.getElementById('id_limit_date');
    if (!retirada || !devolucao) {
        return;
    }

    const prazo = Number(devolucao.dataset.prazoDiasUteis);
    // intervalo amplo calculado pelo servidor, usado quando a retirada está vazia
    const minPadrao = devolucao.min;
    const maxPadrao = devolucao.max;

    function paraData(texto) {
        const [ano, mes, dia] = texto.split('-').map(Number);
        return new Date(ano, mes - 1, dia);
    }

    function paraTexto(data) {
        const mes = String(data.getMonth() + 1).padStart(2, '0');
        const dia = String(data.getDate()).padStart(2, '0');
        return `${data.getFullYear()}-${mes}-${dia}`;
    }

    function somarDiasUteis(data, dias) {
        const resultado = new Date(data);
        while (dias > 0) {
            resultado.setDate(resultado.getDate() + 1);
            const diaDaSemana = resultado.getDay();
            if (diaDaSemana !== 0 && diaDaSemana !== 6) {
                dias -= 1;
            }
        }
        return resultado;
    }

    function atualizar() {
        if (!retirada.value) {
            devolucao.min = minPadrao;
            devolucao.max = maxPadrao;
            return;
        }
        devolucao.min = retirada.value;
        devolucao.max = paraTexto(somarDiasUteis(paraData(retirada.value), prazo));
    }

    retirada.addEventListener('input', atualizar);
    retirada.addEventListener('change', atualizar);
    atualizar();
})();