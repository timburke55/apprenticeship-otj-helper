# Apprenticeship OTJ Helper

A Flask web app for tracking Off-the-Job (OTJ) training activities for the **Systems Thinking Practitioner Level 7 (ST0787)** apprenticeship.

It lets you log training activities, track hours, and map your work to the Knowledge, Skills, and Behaviours (KSBs) required by the standard — so you always know where you stand against each competency.

## Features

- **Dashboard** — total hours logged, breakdown by activity type, recent activities, and KSB coverage at a glance
- **Activity log** — create, edit, and delete training entries with date, duration, type, and free-text notes
- **KSB mapping** — tag each activity against one or more KSBs (K1–K5, S1–S6, B1–B4) from the ST0787 standard
- **Resource links** — attach URLs to activities and organise them using the **CORE workflow** (Capture → Organise → Review → Engage), with support for Google Keep, Google Tasks, Google Docs, Google Drive, GitHub, and more
- **KSB reference** — browse the full ST0787 KSB catalogue, with hours and activity counts per competency

## Tech stack

- **Python 3.11+** / **Flask 3.0+**
- **Flask-SQLAlchemy** with **SQLite** (local) / **PostgreSQL** (production)
- **Tailwind CSS** (CDN)
- **UV** for dependency management

## Getting started (local)

```bash
# Install dependencies
uv sync

# Run the app
uv run otj-helper
```

Then open [http://localhost:5000](http://localhost:5000).

The SQLite database is created automatically at `data/otj.db` on first run and KSB reference data is seeded automatically.

### Local login (no Google OAuth needed)

Set `DEV_AUTO_LOGIN_EMAIL` to any email address and the app will automatically create and log in a local user, bypassing the Google OAuth flow entirely:

```bash
DEV_AUTO_LOGIN_EMAIL=you@example.com uv run otj-helper
```

The user is created on first run and reused on subsequent runs. Unset the variable (or leave it empty) to use normal Google OAuth.

## Deploying to Railway

### 1. Create a Google OAuth app

1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth 2.0 Client ID**, choose **Web application**
3. Under **Authorised redirect URIs**, add:
   ```
   https://<your-app>.railway.app/auth/callback
   ```
   (You can come back and add this once Railway gives you a domain)
4. Copy the **Client ID** and **Client Secret**

### 2. Create a Railway project

1. Go to [railway.app](https://railway.app) and create a new project
2. Connect your GitHub repo and select this repository
3. Railway will detect the `Procfile` and deploy automatically

### 3. Add a PostgreSQL database

In your Railway project, click **+ New** → **Database** → **PostgreSQL**.
Railway sets `DATABASE_URL` in your app's environment automatically — no further config needed.

### 4. Set environment variables

In Railway, go to your service → **Variables** and add:

| Variable | Value |
|---|---|
| `SECRET_KEY` | A long random string (e.g. `openssl rand -hex 32`) |
| `GOOGLE_CLIENT_ID` | From step 1 |
| `GOOGLE_CLIENT_SECRET` | From step 1 |
| `ALLOWED_EMAILS` | Comma-separated list of permitted Google account emails |

**`ALLOWED_EMAILS` example:**
```
you@gmail.com,colleague@work.com,friend@example.com
```

If `ALLOWED_EMAILS` is not set, any Google account can sign in. Set it before going live.

### 5. Update the OAuth redirect URI

Once Railway assigns your app a domain, go back to Google Cloud Console and confirm the redirect URI matches exactly:
```
https://<your-app>.railway.app/auth/callback
```

### Adding or removing users

Edit the `ALLOWED_EMAILS` variable in Railway's dashboard. Changes take effect immediately on the next sign-in attempt — no redeploy needed.

---

## Local configuration

| Environment variable | Default | Description |
|---|---|---|
| `OTJ_DB_PATH` | `data/otj.db` | Path to the SQLite database file (local only) |
| `SECRET_KEY` | `dev-key-change-in-production` | Flask session secret key |
| `DEV_AUTO_LOGIN_EMAIL` | — | Auto-login as this email locally, bypassing Google OAuth |
| `GOOGLE_CLIENT_ID` | — | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | — | Google OAuth client secret |
| `ALLOWED_EMAILS` | — | Comma-separated allowlist (unset = allow all) |
| `DATABASE_URL` | — | PostgreSQL URL (overrides SQLite when set) |

## Activity types

Training course, self study, mentoring, shadowing, workshop, conference, project work, research, writing, and other.

## KSB categories

The ST0787 standard defines 15 competencies across three categories:

- **Knowledge** (K1–K5) — shown in blue
- **Skills** (S1–S6) — shown in green
- **Behaviours** (B1–B4) — shown in yellow
