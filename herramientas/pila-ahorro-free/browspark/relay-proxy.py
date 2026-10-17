"""Relay HTTP proxy local para Browspark/Chromium.

Escucha en 127.0.0.1:3130 sin auth e inyecta Proxy-Authorization con el
token ACTUAL del entorno hacia hatch-egress-proxy:3128. Chrome no acepta
credenciales en --proxy-server, por eso este relay intermedio.

Uso: python3 relay-proxy.py   (lee https_proxy del entorno al arrancar)
"""
import base64
import os
import socket
import threading
import urllib.parse

LOCAL_PORT = 3130


def get_upstream():
    url = os.environ.get("https_proxy") or os.environ.get("http_proxy")
    p = urllib.parse.urlparse(url)
    creds = f"{urllib.parse.unquote(p.username)}:{urllib.parse.unquote(p.password)}"
    auth = "Basic " + base64.b64encode(creds.encode()).decode()
    return p.hostname, p.port or 3128, auth


UP_HOST, UP_PORT, UP_AUTH = get_upstream()
print(f"relay 127.0.0.1:{LOCAL_PORT} -> {UP_HOST}:{UP_PORT} (auth inyectado)", flush=True)

# Rastreadores de publicidad/analytics: no se reenvian (evita prompts de
# permiso, acelera la carga y ahorra tokens en el agente)
BLOCKED = [
    "doubleclick.net", "googlesyndication.com", "googleadservices.com",
    "google-analytics.com", "googletagmanager.com", "33across.com",
    "360yield.com", "yellowblue.io", "syncingbridge.com", "adsrvr.org",
    "criteo.com", "criteo.net", "outbrain.com", "taboola.com",
    "scorecardresearch.com", "quantserve.com", "hotjar.com",
    "amazon-adsystem.com", "ads.yahoo.com", "moatads.com", "iasds01.com",
    "demdex.net", "mathtag.com", "rubiconproject.com", "pubmatic.com",
    "openx.net", "smartadserver.com", "adnxs.com", "lijit.com",
]


def bloqueado(host):
    h = (host or "").lower()
    return any(b in h for b in BLOCKED)


def relay(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass


def handle(client):
    try:
        # Leer cabeceras de la peticion
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = client.recv(4096)
            if not chunk:
                client.close()
                return
            buf += chunk
            if len(buf) > 65536:
                client.close()
                return
        head, _, rest = buf.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        method, target, version = lines[0].split(" ", 2)

        # Host objetivo: CONNECT host:puerto o URL absoluta
        if method.upper() == "CONNECT":
            host = target.split(":")[0]
        else:
            host = urllib.parse.urlparse(target).hostname or ""
            if not host:
                for ln in lines[1:]:
                    if ln.lower().startswith("host:"):
                        host = ln.split(":", 1)[1].strip()
                        break

        if bloqueado(host):
            client.sendall(b"HTTP/1.1 403 Bloqueado\r\nContent-Length: 0\r\n\r\n")
            client.close()
            return

        upstream = socket.create_connection((UP_HOST, UP_PORT), timeout=20)

        # Reenviar la peticion agregando Proxy-Authorization
        out_lines = [lines[0]]
        has_auth = False
        for ln in lines[1:]:
            if ln.lower().startswith("proxy-authorization:"):
                has_auth = True
                continue
            out_lines.append(ln)
        out_lines.append(f"Proxy-Authorization: {UP_AUTH}")
        upstream.sendall(("\r\n".join(out_lines) + "\r\n\r\n").encode("latin-1"))
        if rest:
            upstream.sendall(rest)

        t1 = threading.Thread(target=relay, args=(client, upstream), daemon=True)
        t2 = threading.Thread(target=relay, args=(upstream, client), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    except Exception:
        pass
    finally:
        try:
            client.close()
        except OSError:
            pass


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", LOCAL_PORT))
    srv.listen(50)
    while True:
        client, _ = srv.accept()
        threading.Thread(target=handle, args=(client,), daemon=True).start()


if __name__ == "__main__":
    main()
