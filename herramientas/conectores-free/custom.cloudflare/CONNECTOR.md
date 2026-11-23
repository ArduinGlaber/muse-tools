# Cloudflare Workers AI

- `custom.cloudflare` connects Muse to Cloudflare Workers AI (OpenAI-compatible chat completions). It authenticates with the registered API token via Bearer header and calls only `api.cloudflare.com`.

- Helpers live in `~/workspace/custom-connectors/custom.cloudflare/bin/`. `test_cloudflare.py` sends one text prompt to a Workers AI model and prints the reply, finish reason and token/neuron usage.

## Connect

- The connection was registered with `credentials.request_api_access` and these details. Reuse them unchanged to reconnect:

```json
{
  "provider": "cloudflare",
  "auth_scheme": "api_key",
  "placement": "bearer_header",
  "api_hosts": ["api.cloudflare.com"]
}
```

- The token needs Workers AI Read/Edit permissions. Create it at dash.cloudflare.com → My Profile → API Tokens.

- Before the first change in a conversation, prove access with a harmless read:

```text
python3 ~/workspace/custom-connectors/custom.cloudflare/bin/test_cloudflare.py "Responde solo con la palabra: OK"
```

## Credentials

- The registered connection holds the credential. Helpers import `/opt/muse/skills/custom-connector-setup/bin/dynamic_credentials.py`, which returns an `hsurr:` surrogate and places it where the provider reads the key. Muse swaps in the real credential only on an approved request to a registered host.

- Never put a key, token, password or cookie in this doc, a helper, a command argument, an environment variable or a log. Never ask the user to paste one in chat.

- Keep redirects disabled on authenticated requests.

- On a 401 or 403, check the request first. Confirm that the helper attached the credential, that the host is registered and that the placement and scopes match.

- Only when a request that carried the credential is still rejected, call `credentials.request_api_access` with the details above and `"reconnect": true`.

## Send a text prompt (verified 2026-10-18)

- Sends one prompt to a Workers AI model (default `@cf/meta/llama-3.3-70b-instruct-fp8-fast`) and returns the text reply. Read only, no side effects.

```text
python3 ~/workspace/custom-connectors/custom.cloudflare/bin/test_cloudflare.py "tu pregunta aquí" [modelo] [account_id]
```

- The Account ID goes in the URL path. The helper tries to discover it via `GET /accounts`; if that returns empty (token without account-listing scope), pass the Account ID explicitly as the third argument. The user's Account ID is in the Cloudflare dashboard sidebar.

- Output fields: `http` (200 on success), `account_id`, `model`, `reply`, `finish_reason`, `usage` (token counts plus `neurons` consumed).

- Verified: HTTP 200 on a basic prompt and on a technical solar-installation calculation. Replies arrive in the requested language. Free tier: 10,000 Neurons/day, no credit card.

## Recover from errors

- 410 with `Model has been deprecated` means the model id is retired. Check the current catalog at developers.cloudflare.com/workers-ai/models. `@cf/meta/llama-3.1-8b-instruct` was deprecated 2026-05-30; `@cf/meta/llama-3.3-70b-instruct-fp8-fast` verified working 2026-10-18.

- Empty `/accounts` result with `success: true` means the token lacks account-listing scope. Pass the Account ID explicitly instead of relying on discovery.

- 401 means the token is missing, revoked or malformed. Check the helper attached the credential and the host is registered before reconnecting.

- 429 means the rate limit was hit. Wait and retry with backoff.

- After a failed or timed-out change, check the current state with a read before trying again, because the first request may have completed.

## Limits

- This connector cannot manage the Cloudflare account, rotate tokens or check billing. Those actions happen in the Cloudflare dashboard.

- Free tier: 10,000 Neurons/day, no credit card. No token purchase; rate limits are the only constraint.

- Untested: streaming (SSE), image models, embeddings, and the non-OpenAI `/ai/run` endpoint format.

## Cloudflare Pages (Direct Upload)

- Same registered connection and token. The token needs **Account → Cloudflare Pages → Edit**. It does **not** need account-listing scope.

- The Account ID cannot be discovered with this token (`GET /accounts` returns an empty list). Pass it explicitly; it is in the Cloudflare dashboard sidebar, next to the account name. Every Pages endpoint needs it in the path.

- The browser route is blocked: the Cloudflare login page's Turnstile check fails systematically in the cloud browser (verified 2026-11-16), so deployments go through this API route instead. Never retry the dashboard login for a deploy.

- Helper: `~/workspace/custom-connectors/custom.cloudflare/bin/deploy_pages.py`. It creates the project via the API, then deploys the directory with wrangler (Node 24 available; `npx -y wrangler@latest`). The surrogate reaches wrangler as `CLOUDFLARE_API_TOKEN`; authd swaps it for the real token on requests to `api.cloudflare.com`. No credential is written to disk, arguments or logs.

```text
python3 ~/workspace/custom-connectors/custom.cloudflare/bin/deploy_pages.py \
  --dir ~/workspace/lumos/web --account-id <ID> [--project <nombre>]
```

- Without `--project` it tries names in order: `lumos`, `lumos-energia`, `lumos-respaldos`. A name already taken by another account is skipped; a project that already exists under this account is reused.

- After deploying, verify the live URL (`https://<project>.pages.dev`) loads without VPN from the user's phone: the page, the logo and the WhatsApp links. No country-blocking rules, no Workers Functions — static site only.

- First deployment (LUMOS web, `~/workspace/lumos/web/` with `index.html` + `logo.png`): PENDING the Account ID from the user (asked 2026-11-16 17:26 Habana).

## Related skills

- Use `muse.skill_search` to find other skills and `muse.connector_search` to find other connectors.
