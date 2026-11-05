import ipaddress


def _valid_ip(ip):
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return False
    return True

def get_client_ip(request):
    if request is None:
        return None
    # atrás do proxy do Render, REMOTE_ADDR é o IP do proxy; o IP do cliente
    # vem no início de X-Forwarded-For.
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        ip = forwarded.split(',')[0].strip()
        if _valid_ip(ip):
            return ip
    remote = request.META.get('REMOTE_ADDR')
    return remote if remote and _valid_ip(remote) else None