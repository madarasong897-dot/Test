# GOD TOJI — Railway-ready bot dashboard

This package keeps the existing account, clan tracker, and match-worker code with the GOD TOJI dashboard and Docker support. The dashboard starts with no clan selected. Saving a clan ID is required before clan details load or any clan-join requests can be sent. Adding an account after a clan is saved triggers a join request after that account logs in. Gameplay waits until the selected clan's returned member roster confirms that every saved account is a member; a submitted request alone does not count as approval. If the roster cannot be verified, the account workers remain in `WAITING_CLAN`. If an account is added during a match, that match may finish, but the next match waits for membership confirmation. Saved accounts are assigned in saved order to independent squads of four; a final group with fewer than four accounts waits until it is filled. Run, Stop, and Restart control all account worker tasks; Stop cancels all workers, and Restart starts them again from the saved account list.

## Movement phase 1

In a match, every account's movement worker continuously cycles through walk, run, sprint, and jump while following circle, zigzag, straight, strafe, and smooth-random paths around a shared virtual center, with a small formation offset per saved account. The movement worker stops when the match itself ends. This project does not yet read live player positions or the safe-zone center/radius, so the formation is best-effort and does not guarantee that players stay inside the safe zone. After a match, the account keeps its gateway session open and queues for the next match without an intentional offline/reconnect delay.

The Docker image installs requirements, starts `app.py`, binds to Railway's assigned `PORT`, and stores runtime JSON under `/app/data`.

## Import accounts from JSON

In the signed-in dashboard, use **Add account** to choose a `.json` file or paste JSON content directly. The content can be a single account object, a JSON array, or an object containing an `accounts` array. Each entry must contain either `uid` and `password`, or a `token`. Imports are limited to 500 entries at a time; invalid rows and accounts already saved are skipped and summarized in the dashboard. Duplicate entries do not replace saved credentials.

```json
[
  {"uid": "account-id", "password": "account-password"},
  {"token": "account-access-token"}
]
```

Account JSON contains login credentials or access tokens. Keep it private and upload it only through your own authenticated dashboard.

## Deploy on Railway

1. Extract this ZIP and upload its contents to a **private** GitHub repository. Do not add your account/token JSON files.
2. In Railway, choose **New Project → GitHub Repo** and select the repository. Railway will build the included `Dockerfile`.
3. In the service's **Variables**, set:
   - `DASHBOARD_USERNAME` — dashboard login username (for example, `admin`).
   - `DASHBOARD_PASSWORD` — a unique, strong password. Keep it in Railway Variables, not GitHub.
   - `SESSION_SECRET` — recommended: a long, random secret used to sign dashboard sessions. If omitted, the dashboard password is used as a compatibility signing key.
4. Add a Railway **Volume** to this service and set its mount path to `/app/data`. This keeps accounts, tokens, device IDs, selected clan settings, and XP cache across restarts.
5. Deploy/redeploy after the settings are applied. The Docker image starts `python app.py`; Railway supplies `PORT`.
6. In **Settings → Networking**, click **Generate Domain**. Open the HTTPS domain and sign in on the dashboard's username/password page. Sessions use an HttpOnly cookie and expire after 12 hours. You can optionally set the service healthcheck path to `/health`.

## Local run

Run `docker compose up --build` and open `http://localhost:8080`; local Compose runs without a password by default and binds only to `127.0.0.1`. To test the username/password page locally, copy `.env.example` to `.env`, replace the placeholder values, and run Compose again. `.env` is ignored by Git; never commit real credentials. The passwordless flag is local-only. Do not add `DASHBOARD_ALLOW_PASSWORDLESS_LOCAL` to Railway. The Compose volume preserves runtime data. Railway still requires `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD`.

## Account data and privacy

The source archive used to prepare this package contained runtime account, token, and device JSON files. Those files are intentionally not included in this shareable package. Add accounts again in the dashboard, or transfer your existing JSON files privately into the configured data directory. Never commit account passwords or cached tokens to GitHub.

Use a private GitHub repository. Railway's public HTTPS URL makes the dashboard reachable, so keep the login credentials private. Clan-join requests are sent only after a clan is explicitly saved in the dashboard. Docker automates the build and app start; creating the Railway service, adding its variables and volume, and generating its public domain are still one-time Railway dashboard steps.
