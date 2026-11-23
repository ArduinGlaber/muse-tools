# Nvidia

- `custom.nvidia` connects Muse to the Nvidia NIM API at `https://integrate.api.nvidia.com`. It authenticates with the registered `api_key` credential sent as a Bearer header.

- Helpers live in `~/workspace/custom-connectors/custom.nvidia/bin/`. `test_nvidia.py` sends a chat completion (prompt as first arg, model as second arg) and registers usage in `~/workspace/cuotas/cuotas.py`.

## Connect

- The connection was registered with `credentials.request_api_access` and these details. Reuse them unchanged to reconnect:

```json
{
  "provider": "nvidia",
  "auth_scheme": "api_key",
  "placement": "bearer_header",
  "api_hosts": ["integrate.api.nvidia.com"]
}
```

- Before the first change in a conversation, prove access with a harmless read:

```text
python3 ~/workspace/custom-connectors/custom.nvidia/bin/test_nvidia.py "Responde solo con la palabra: OK" "<modelo>"
```

- A cheaper read that needs no model: `GET https://integrate.api.nvidia.com/v1/models` lists the catalog (verified 2026-10-19: 81 models).

## Credentials

- The registered connection holds the credential. Helpers import `/opt/muse/skills/custom-connector-setup/bin/dynamic_credentials.py`, which returns an `hsurr:` surrogate and places it where the provider reads the key. Muse swaps in the real credential only on an approved request to a registered host.

- Never put a key, token, password or cookie in this doc, a helper, a command argument, an environment variable or a log. Never ask the user to paste one in chat.

- Keep redirects disabled on authenticated requests.

- On a 401 or 403, check the request first. Confirm that the helper attached the credential, that the host is registered and that the placement and scopes match.

- Only when a request that carried the credential is still rejected, call `credentials.request_api_access` with the details above and `"reconnect": true`.

## Chat completion

- Sends one chat completion to Nvidia NIM. Verified 2026-10-19: the stored key works end to end with `z-ai/glm-5.3-flash` (HTTP 200, usage logged to `~/workspace/cuotas/`).

```text
python3 ~/workspace/custom-connectors/custom.nvidia/bin/test_nvidia.py "<prompt>" "<modelo>"
```

- Default model is `z-ai/glm-5.3-flash` (Free Endpoint, fast). `deepseek-ai/deepseek-v4.1-flash` timed out twice from this network (up to 180 s) — avoid it here.

- If a model returns 404 `Function ... Not found for account`, it is not enabled for this account: enable it at build.nvidia.com (needs a "Free Endpoint" badge) or pick another from `/v1/models`.

## Recover from errors

- 404 `Function ... Not found for account` means the model is not enabled for this account. Enable it at build.nvidia.com; no retry will fix it from here.

- 410 `Gone` means the model reached end of life (seen 2026-10-19 with `meta/llama-3.1-8b-instruct`, EOL 2026-08-26). Pick a current model from `/v1/models`.

- After a failed or timed-out change, check the current state with a read before trying again, because the first request may have completed.

## Limits

- Verified 2026-10-19: key works end to end with `z-ai/glm-5.3-flash`. Free tier (Oct 2026): no more signup credits (the old 1,000-credit pool was removed — now "unlimited requests"); the real caps are ~40 requests/minute and 10,000 requests/day per account. No card; needs an NVIDIA Developer Program account with phone verification in a supported country. Only models with the "Free Endpoint" badge work on the free tier. Full limits in `~/workspace/cuotas/limites.json`.

## Related skills

- Use `muse.skill_search` to find other skills and `muse.connector_search` to find other connectors.
