# OpenRouter

- `custom.openrouter` connects Muse to the OpenRouter REST API. It authenticates with the registered `api_key` credential (Bearer header) and calls only `openrouter.ai`.

- Helpers live in `~/workspace/custom-connectors/custom.openrouter/bin/`. `test_free.py` sends one chat completion through the `openrouter/free` router and prints the picked model, reply and usage.

## Connect

- The connection was registered with `credentials.request_api_access` and these details. Reuse them unchanged to reconnect:

```json
{
  "provider": "openrouter",
  "auth_scheme": "api_key",
  "placement": "bearer_header",
  "api_hosts": ["openrouter.ai"]
}
```

- Before the first change in a conversation, prove access with a harmless read:

```text
python3 ~/workspace/custom-connectors/custom.openrouter/bin/test_free.py
```

## Credentials

- The registered connection holds the credential. Helpers import `/opt/muse/skills/custom-connector-setup/bin/dynamic_credentials.py`, which returns an `hsurr:` surrogate and places it where the provider reads the key. Muse swaps in the real credential only on an approved request to a registered host.

- Never put a key, token, password or cookie in this doc, a helper, a command argument, an environment variable or a log. Never ask the user to paste one in chat.

- Keep redirects disabled on authenticated requests.

- On a 401 or 403, check the request first. Confirm that the helper attached the credential, that the host is registered and that the placement and scopes match.

- Only when a request that carried the credential is still rejected, call `credentials.request_api_access` with the details above and `"reconnect": true`.

## Test the free router (verified 2026-10-16)

- Sends one request to `POST https://openrouter.ai/api/v1/chat/completions` with `model: openrouter/free`. Read only, costs nothing.

```text
python3 ~/workspace/custom-connectors/custom.openrouter/bin/test_free.py
```

- Output fields: `http` (200 on success), `model` (which free model the router picked), `reply`, `finish_reason`, `usage` (token counts, `cost` is 0 for free models).

- Verified: HTTP 200, router picked `nvidia/nemotron-3.5-content-safety:free`, cost 0. The router picks a random free model per request, so the picked model varies.

## Check key limits (verified 2026-10-16)

- `GET https://openrouter.ai/api/v1/key` returns the key record under `data`. Read `data.free_model_daily_requests` (`used`, `limit`, `remaining`) and `data.is_free_tier`.

- Verified on this account: `is_free_tier: true`, `free_model_daily_requests.limit: 50`. The 50/day counter covers all `:free` models together, not per model. With 10 or more credits purchased lifetime it becomes 1000/day.

## Recover from errors

- 401 means the key is missing, revoked or malformed. Check the helper attached the credential and the host is registered before reconnecting.

- 402 means the account balance cannot cover a paid request. Free `:free` models do not charge.

- 429 on a free model means the free-tier rate limit was hit (20 req/min, 50 or 1000 req/day depending on credits purchased). Wait and retry with backoff. Provider-side 429s may carry `error.metadata.provider_code`.

## Limits

- This connector cannot buy credits, manage the account or rotate keys. Those actions happen on the OpenRouter website.

- Untested: chat completions with a specific paid model, streaming (SSE), and the `/api/v1/models` catalog listing.

## Related skills

- Use `muse.skill_search` to find other skills and `muse.connector_search` to find other connectors.
