from contextvars import ContextVar

_request_atual = ContextVar('request_atual', default=None)


def get_request_atual():
    # request é None fora de uma requisição
    return _request_atual.get()


class RequestAtualMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _request_atual.set(request)
        try:
            return self.get_response(request)
        finally:
            _request_atual.reset(token)