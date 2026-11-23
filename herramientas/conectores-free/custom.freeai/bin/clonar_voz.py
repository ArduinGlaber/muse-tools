"""Clona una voz y genera audio con ella (Free.ai).

Uso:
  python3 clonar_voz.py muestra.wav "texto a hablar" [modelo] [salida.mp3]

Sube la muestra de voz (10-60s, wav/mp3/m4a/ogg/flac), encola el trabajo
de clonación+TTS y espera el audio resultante. Modelos: chatterbox
(defecto), openvoice, qwen3-tts.
"""
import json, sys, time, urllib.request, uuid
sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
sys.path.insert(0, "/home/hatch/workspace/cuotas")
from dynamic_credentials import add_surrogate_to_request, read_json_response
import cuotas

BASE = "https://api.free.ai"
HOSTS = ["api.free.ai"]
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")

def _req(url, data=None, headers=None, method="GET"):
    r = urllib.request.Request(url, data=data,
                               headers={**UA, **(headers or {})}, method=method)
    add_surrogate_to_request(r, "custom.freeai", allowed_hosts=HOSTS)
    return r

def clonar(audio_path, texto, model="chatterbox", salida=None, espera_max=600):
    boundary = "----" + uuid.uuid4().hex
    audio = open(audio_path, "rb").read()
    def field(name, value, filename=None, ctype=None):
        h = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
        if filename:
            h += f'; filename="{filename}"\r\nContent-Type: {ctype}'
        h += "\r\n\r\n"
        v = value if isinstance(value, bytes) else value.encode()
        return h.encode() + v + b"\r\n"
    body = (field("audio", audio, "muestra.wav", "audio/wav") +
            field("text", texto) + field("model", model) +
            f"--{boundary}--\r\n".encode())
    req = _req(BASE + "/v1/voice/clone/", data=body,
               headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
               method="POST")
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=120) as r:
        d = read_json_response(r)
    job_id = d.get("job_id")
    if not job_id:
        print(json.dumps({"http": "error", "body": d}, ensure_ascii=False)[:500])
        sys.exit(1)
    print(f"Trabajo encolado: {job_id} (posición {d.get('position_in_queue')})",
          flush=True)
    t0 = time.time()
    while time.time() - t0 < espera_max:
        time.sleep(15)
        req = _req(f"{BASE}/v1/status/{job_id}")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                st = json.loads(r.read())
        except Exception as e:
            print("  estado: error consultando", e, flush=True)
            continue
        estado = str(st.get("status", "")).lower()
        print(f"  estado: {estado}", flush=True)
        if estado in ("completed", "done", "success", "finished"):
            url_audio = (st.get("audio_url") or st.get("url") or
                         st.get("result", {}).get("audio_url") if isinstance(st.get("result"), dict) else None)
            print(json.dumps({"http": 200, "job_id": job_id,
                              "audio_url": url_audio,
                              "status": st}, ensure_ascii=False)[:800])
            if url_audio and salida:
                req = _req(url_audio)
                with urllib.request.urlopen(req, timeout=120) as r:
                    open(salida, "wb").write(r.read())
                print("Audio guardado en", salida)
            cuotas.registrar("freeai", "voice-clone/" + model, 200)
            return
        if estado in ("failed", "error"):
            print("Falló:", json.dumps(st)[:500])
            cuotas.registrar("freeai", "voice-clone/" + model, "error")
            sys.exit(1)
    print("Timeout esperando el trabajo; consúltalo luego con:")
    print(f"  curl -H \"Authorization: Bearer $KEY\" {BASE}/v1/status/{job_id}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    clonar(sys.argv[1], sys.argv[2],
           sys.argv[3] if len(sys.argv) > 3 else "chatterbox",
           sys.argv[4] if len(sys.argv) > 4 else None)
