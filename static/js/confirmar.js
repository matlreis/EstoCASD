// Pede confirmação antes de enviar qualquer formulário com o atributo data-confirm.
document.addEventListener('submit', (event) => {
    const mensagem = event.target.dataset.confirm;
    if (mensagem && !window.confirm(mensagem)) {
        event.preventDefault();
    }
});
