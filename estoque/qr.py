import io
import segno


def montar_qr_code(url):
    # QR code padrão, com correção de erros de nível Q, no mínimo: tolera adesivo sujo ou riscado.
    # O segno sobe para H sozinho quando isso não aumenta o tamanho do código.
    return segno.make_qr(url, error='q')


def qr_code_png(url):
    buffer = io.BytesIO()
    montar_qr_code(url).save(buffer, kind='png', scale=20, border=4)
    return buffer.getvalue()