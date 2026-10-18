"""Relay HTTP proxy local para Browspark/Chromium.

Escucha en 127.0.0.1:3130 sin auth e inyecta Proxy-Authorization con el
token ACTUAL del entorno hacia hatch-egress-proxy:3128. Chrome no acepta
credenciales en --proxy-server, por eso este relay intermedio.

Uso: python3 relay-proxy.py   (lee https_proxy del entorno al arrancar)

Fix 2026-10-18 (DeepSeek): header timeout para preconnects de Chromium.
"""
import base64
import errno
import os
import socket
import threading
import time
import urllib.parse

LOCAL_PORT = 3130
HEADER_TIMEOUT = 10.0
MAX_CONCURRENT = 200

slots = threading.BoundedSemaphore(MAX_CONCURRENT)


def recv_until(sock, delim, deadline):
    """Lee hasta delim con deadline. Sin esto, los preconnects de Chromium
    (sockets que nunca envian datos) dejan hilos bloqueados para siempre."""
    buf = b""
    while delim not in buf:
        remain = deadline - time.monotonic()
        if remain <= 0:
            raise socket.timeout("header deadline")
        sock.settimeout(remain)
        chunk = sock.recv(65536)
        if not chunk:
            raise ConnectionError("eof in headers")
        buf += chunk
        if len(buf) > 256 * 1024:
            raise ValueError("headers too big")
    head, _, rest = buf.partition(delim)
    return head, rest


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


def relay(src, dst, done):
    """Copia bytes hasta EOF o hasta que la otra dirección termine.
    Al terminar, marca done y cierra AMBOS sockets para liberar al otro
    hilo (sin esto, el hilo gemelo queda bloqueado en recv() para siempre
    y el socket del cliente muere en CLOSE-WAIT: fuga de hilos y FDs)."""
    try:
        while not done.is_set():
            try:
                data = src.recv(65536)
            except socket.timeout:
                continue
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        done.set()
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass


def handle(client):
    import time as _t
    _t0 = _t.monotonic()
    _marks = {}
    _target = "?"  # para el slow-log aunque falle antes de parsear
    def _mark(name):
        _marks[name] = round(_t.monotonic() - _t0, 2)
    try:
        # Leer cabeceras con deadline: los preconnects no fugan hilos
        head, rest = recv_until(client, b"\r\n\r\n",
                               _t.monotonic() + HEADER_TIMEOUT)
        _mark("headers")
        lines = head.decode("latin-1").split("\r\n")
        method, target, version = lines[0].split(" ", 2)
        _target = target

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
        _mark("upstream_connect")
        # TCP_NODELAY: evita que Nagle retenga el CONNECT en el buffer
        # (2026-10-18: causa profunda del "wedge" es el egress lento en
        # DNS/IPv6, no nuestro codigo; esto elimina nuestra parte del delay)
        try:
            upstream.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass

        # Reenviar la peticion agregando Proxy-Authorization
        out_lines = [lines[0]]
        for ln in lines[1:]:
            if ln.lower().startswith("proxy-authorization:"):
                continue
            out_lines.append(ln)
        out_lines.append(f"Proxy-Authorization: {UP_AUTH}")
        upstream.sendall(("\r\n".join(out_lines) + "\r\n\r\n").encode("latin-1"))
        if rest:
            upstream.sendall(rest)

        # Mirar la primera respuesta: 407 = token podrido -> morir para que
        # el supervisor reinicie con token fresco (codigo 42)
        # Timeout 8s: si el egress no responde al CONNECT, fallar rapido con
        # 502 antes de que el cliente (10s) se rinda.
        upstream.settimeout(8)
        try:
            primero = upstream.recv(4096)
        except socket.timeout:
            primero = b""
        if b" 407 " in primero[:60]:
            try:
                client.sendall(b"HTTP/1.1 407 Proxy Auth Required\r\n"
                              b"Content-Length: 0\r\n\r\n")
            except OSError:
                pass
            client.close()
            upstream.close()
            print("token podrido (407 del upstream), saliendo", flush=True)
            os._exit(42)
        upstream.settimeout(None)
        _mark("peek")
        if not primero:
            # El egress no respondio al CONNECT en 15s: fallar rapido con 502
            # en vez de colgar el tunel (el cliente reintenta).
            try:
                client.sendall(b"HTTP/1.1 502 Egress lento\r\n"
                              b"Content-Length: 0\r\n\r\n")
            except OSError:
                pass
            client.close()
            upstream.close()
            return
        try:
            client.sendall(primero)
        except OSError:
            client.close()
            upstream.close()
            return

        # Timeout de inactividad: las conexiones ociosas se recogen solas
        client.settimeout(120)
        upstream.settimeout(120)
        done = threading.Event()
        t1 = threading.Thread(target=relay, args=(client, upstream, done),
                              daemon=True)
        t2 = threading.Thread(target=relay, args=(upstream, client, done),
                              daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        _mark("done")
    except Exception:
        pass
    finally:
        try:
            total = round(_t.monotonic() - _t0, 2)
        except Exception:
            total = -1
        # Log de peticiones lentas: para cazar donde se pierden los 10s
        # Incluye el host objetivo para detectar si es especifico de un destino
        if total is not None and total > 5:
            try:
                with open("/home/hatch/workspace/browspark/relay-slow.log",
                          "a") as _lf:
                    _lf.write(f"{_t.strftime('%F %T', _t.gmtime())} "
                              f"total={total}s marks={_marks} "
                              f"target={_target}\n")
            except OSError:
                pass
        try:
            client.close()
        except OSError:
            pass
        try:
            upstream.close()
        except (OSError, NameError):
            pass
        slots.release()


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", LOCAL_PORT))
    srv.listen(128)
    srv.settimeout(1.0)
    while True:
        try:
            client, _ = srv.accept()
        except socket.timeout:
            continue
        except OSError as e:
            if e.errno in (errno.EMFILE, errno.ENFILE):
                time.sleep(1.0)  # backoff, NO morir
                continue
            time.sleep(0.1)
            continue

        if not slots.acquire(blocking=False):
            try:
                client.sendall(b"HTTP/1.1 503 Busy\r\n\r\n")
            except OSError:
                pass
            client.close()
            continue

        try:
            threading.Thread(target=handle, args=(client,),
                             daemon=True).start()
        except RuntimeError:  # can't start new thread
            slots.release()
            client.close()
            time.sleep(0.5)


if __name__ == "__main__":
    main()
