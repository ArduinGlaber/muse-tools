# Groq

- `custom.groq` connects Muse to the Groq Cloud API (OpenAI-compatible chat completions). It authenticates with the registered `api_key` credential via Bearer header and calls only `api.groq.com`.

- Helpers live in `~/workspace/custom-connectors/custom.groq/bin/`. `test_groq.py` sends one text prompt to a Groq model and prints the reply, finish reason and token usage.

## Connect

- The connection was registered with `credentials.request_api_access` and these details. Reuse them unchanged to reconnect:

```json
{
  "provider": "groq",
  "auth_scheme": "api_key",
  "placement": "bearer_header",
  "api_hosts": ["api.groq.com"]
}
```

- Before the first change in a conversation, prove access with a harmless read:

```text
python3 ~/workspace/custom-connectors/custom.groq/bin/test_groq.py "Responde solo con la palabra: OK"
```

## Credentials

- The registered connection holds the credential. Helpers import `/opt/muse/skills/custom-connector-setup/bin/dynamic_credentials.py`, which returns an `hsurr:` surrogate and places it where the provider reads the key. Muse swaps in the real credential only on an approved request to a registered host.

- Never put a key, token, password or cookie in this doc, a helper, a command argument, an environment variable or a log. Never ask the user to paste one in chat.

- Keep redirects disabled on authenticated requests.

- On a 401 or 403, check the request first. Confirm that the helper attached the credential, that the host is registered and that the placement and scopes match.

- Only when a request that carried the credential is still rejected, call `credentials.request_api_access` with the details above and `"reconnect": true`.

## Send a text prompt (verified 2026-10-18)

- Sends one prompt to a Groq model (default `openai/gpt-oss-20b`; `openai/gpt-oss-120b` also verified working on the free tier) and returns the text reply. Read only, no side effects.

```text
python3 ~/workspace/custom-connectors/custom.groq/bin/test_groq.py "tu pregunta aquí" [modelo]
```

- Output fields: `http` (200 on success), `model`, `reply` (the text response), `finish_reason`, `usage` (token counts plus Groq timing fields like `total_time`).

- Verified: HTTP 200 on a basic prompt and on a technical solar-installation calculation (breaker sizing for 4x Longi 615W panels, MPPT 230V/60A, 72V battery). Replies arrive in the requested language. Typical latency under 2 seconds.

## Recover from errors

- 403 with `error code: 1010` means Cloudflare blocked the request signature. Python's default `Python-urllib/3.x` User-Agent is rejected; send a browser-like `User-Agent` header instead.

- 400 with `model_not_found` means the model id is wrong or retired. Check the current model list at console.groq.com; free-tier models change over time (Llama models left the free tier in August 2026).

- 401 means the key is missing, revoked or malformed. Check the helper attached the credential and the host is registered before reconnecting.

- 429 means the rate limit was hit (free tier: ~30 req/min per model). Wait and retry with backoff.

- After a failed or timed-out change, check the current state with a read before trying again, because the first request may have completed.

## Limits

- This connector cannot manage the Groq Cloud account, rotate keys or check billing. Those actions happen in the Groq console.

- Free tier has no credit card and no token purchase; rate limits are the only constraint. Limits are per model (RPM/RPD/TPM/TPD); check console.groq.com/docs/rate-limits for the current table.

- Untested: streaming (SSE), JSON mode, tool calling, and audio models (Whisper).

## Related skills

- Use `muse.skill_search` to find other skills and `muse.connector_search` to find other connectors.
