def get_client_ip(request):
    if request is None:
        return None
    # atrás do proxy do Render, REMOTE_ADDR é o IP do proxy; o IP do cliente
    # vem no início de X-Forwarded-For.
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')