# Gemini

- `custom.gemini` connects Muse to the Google Gemini API (Generative Language REST API). It authenticates with the registered `api_key` credential via the `x-goog-api-key` header and calls only `generativelanguage.googleapis.com`.

- Helpers live in `~/workspace/custom-connectors/custom.gemini/bin/`. `test_gemini.py` sends one text prompt to `gemini-2.5-flash` and prints the reply, finish reason and token usage.

## Connect

- The connection was registered with `credentials.request_api_access` and these details. Reuse them unchanged to reconnect:

```json
{
  "provider": "gemini",
  "auth_scheme": "api_key",
  "placement": "custom_header:x-goog-api-key",
  "api_hosts": ["generativelanguage.googleapis.com"]
}
```

- Before the first change in a conversation, prove access with a harmless read:

```text
python3 ~/workspace/custom-connectors/custom.gemini/bin/test_gemini.py "Responde solo con la palabra: OK"
```

## Credentials

- The registered connection holds the credential. Helpers import `/opt/muse/skills/custom-connector-setup/bin/dynamic_credentials.py`, which returns an `hsurr:` surrogate and places it where the provider reads the key. Muse swaps in the real credential only on an approved request to a registered host.

- Never put a key, token, password or cookie in this doc, a helper, a command argument, an environment variable or a log. Never ask the user to paste one in chat.

- Keep redirects disabled on authenticated requests.

- On a 401 or 403, check the request first. Confirm that the helper attached the credential, that the host is registered and that the placement and scopes match.

- Only when a request that carried the credential is still rejected, call `credentials.request_api_access` with the details above and `"reconnect": true`.

## Send a text prompt (verified 2026-10-18)

- Sends one prompt to `gemini-2.5-flash` and returns the text reply. Read only, no side effects.

```text
python3 ~/workspace/custom-connectors/custom.gemini/bin/test_gemini.py "tu pregunta aquí"
```

- Output fields: `http` (200 on success), `model`, `reply` (the text response), `finish_reason`, `usage` (token counts with `promptTokenCount`, `candidatesTokenCount`, `totalTokenCount`).

- Verified: HTTP 200 on a basic prompt and on a technical solar-installation calculation (breaker sizing for 4x Longi 615W panels, MPPT 230V/60A, 72V battery). Replies arrive in the requested language.

## Recover from errors

- 400 with `NOT_FOUND` means the model name is wrong or retired. Check the current model list; `gemini-2.0-flash` was retired and replaced by `gemini-3.8-flash` (2026-10-18); `gemini-3.8-flash` overloaded (503, high demand) 2026-11-23, switched to `gemini-2.5-flash` (200, ~1 s).

- 401 means the key is missing, revoked or malformed. Check the helper attached the credential and the host is registered before reconnecting.

- 429 means the rate limit was hit. Wait and retry with backoff.

- After a failed or timed-out change, check the current state with a read before trying again, because the first request may have completed.

## Limits

- This connector cannot manage the Google Cloud account, rotate keys or check billing. Those actions happen in Google AI Studio / Google Cloud Console.

- Untested: image input, streaming (SSE), function calling, and models other than `gemini-2.5-flash`.

## Related skills

- Use `muse.skill_search` to find other skills and `muse.connector_search` to find other connectors.
