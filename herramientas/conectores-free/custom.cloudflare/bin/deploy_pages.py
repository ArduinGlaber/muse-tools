"""Despliegue de un sitio estatico a Cloudflare Pages (Direct Upload) via wrangler.

El token (custom.cloudflare, permiso Cloudflare Pages: Edit) llega por
surrogate: se pasa a wrangler como CLOUDFLARE_API_TOKEN y el intercambio
con authd lo sustituye por el real en las peticiones a api.cloudflare.com.
No se escribe ninguna credencial en disco, en argumentos visibles ni en logs.

Uso:
  python3 deploy_pages.py --dir ~/workspace/lumos/web --account-id <ID>
  python3 deploy_pages.py --dir <dir> --account-id <ID> --project lumos

- El Account ID NO se puede descubrir con este token (GET /accounts devuelve
  lista vacia: sin permiso para listar cuentas). Hay que pasarlo explicito;
  esta en la barra lateral del dashboard de Cloudflare.
- Sin --project, prueba en orden: lumos, lumos-energia, lumos-respaldos.
  Antes de desplegar crea el proyecto por API; si el nombre ya existe, lo
  verifica con GET y lo reutiliza si es del usuario.
- Imprime JSON con project, url y la salida de wrangler.
"""
import json, subprocess, sys, urllib.error, urllib.request

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request, dynamic_credential_entry, read_json_response

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
NAMES = ["lumos", "lumos-energia", "lumos-respaldos"]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")


def authed(method, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = dict(UA)
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    add_surrogate_to_request(req, "custom.cloudflare", allowed_hosts=["api.cloudflare.com"])
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=60) as r:
            return r.status, read_json_response(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8", "ignore") or "{}")


def ensure_project(account_id, name):
    """Crea el proyecto Pages; si ya existe, verifica que sea del usuario."""
    base = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/pages/projects"
    status, body = authed("POST", base, {"name": name, "production_branch": "main"})
    if status in (200, 201) and body.get("success"):
        return True
    errors = body.get("errors") or []
    msg = " ".join(e.get("message", "") for e in errors)
    if "already exists" in msg or "duplicate" in msg.lower() or status == 409:
        status2, body2 = authed("GET", f"{base}/{name}")
        if status2 == 200 and body2.get("success"):
            return True
        raise RuntimeError(f"el nombre {name} ya esta tomado por otra cuenta "
                           f"(GET proyecto: HTTP {status2})")
    raise RuntimeError(f"no se pudo crear el proyecto {name}: HTTP {status}: {msg[:300]}")


def deploy(account_id, project, directory):
    surrogate = dynamic_credential_entry("custom.cloudflare")["surrogate"]
    env = {"CLOUDFLARE_API_TOKEN": surrogate,
           "CLOUDFLARE_ACCOUNT_ID": account_id,
           "PATH": "/usr/local/bin:/usr/bin:/bin",
           "HOME": "/home/hatch",
           "CI": "true",
           "NO_COLOR": "1"}
    cmd = ["npx", "-y", "wrangler@latest", "pages", "deploy", directory,
           "--project-name", project]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
    out = (proc.stdout + "\n" + proc.stderr)[-4000:]
    return proc.returncode, out


def main():
    args = sys.argv[1:]
    try:
        directory = args[args.index("--dir") + 1]
        account_id = args[args.index("--account-id") + 1]
    except (ValueError, IndexError):
        print("uso: deploy_pages.py --dir <dir> --account-id <ID> [--project <nombre>]")
        sys.exit(2)
    projects = [args[args.index("--project") + 1]] if "--project" in args else NAMES
    last_error = None
    for project in projects:
        try:
            ensure_project(account_id, project)
        except RuntimeError as e:
            last_error = str(e)
            print(f"[{project}] {e}", file=sys.stderr)
            continue
        code, out = deploy(account_id, project, directory)
        url = f"https://{project}.pages.dev"
        print(json.dumps({"project": project, "url": url,
                          "wrangler_exit": code, "output_tail": out[-1500:]},
                         ensure_ascii=False, indent=2))
        if code == 0 and ("pages.dev" in out or "Deployment complete" in out
                          or "https://" in out):
            sys.exit(0)
        last_error = f"wrangler salio con codigo {code} para {project}"
        print(f"[{project}] {last_error}", file=sys.stderr)
    print(json.dumps({"error": last_error or "sin proyecto disponible"},
                     ensure_ascii=False))
    sys.exit(1)


if __name__ == "__main__":
    main()
