# HMS Frontend (React + Vite + Supabase)

Day 1 UI shell: app layout, Gujarati/English language toggle, Supabase Auth
login, and a dashboard that proves the frontend ↔ backend ↔ database chain.

## Prerequisites
- **Node.js 18+** (includes npm) — https://nodejs.org (download the LTS Windows installer).
  After installing, **open a new terminal** so `node`/`npm` are on PATH.
- The backend running at http://127.0.0.1:8000 (see `../backend/README.md`).

## 1. Install
```powershell
cd C:\Users\aarsh\Downloads\mygift\frontend
npm install
```

## 2. Configure
```powershell
Copy-Item .env.example .env
notepad .env
```
Fill in from Supabase (Settings → API):
- `VITE_SUPABASE_URL` = https://atohgsprqqwfujghjyky.supabase.co
- `VITE_SUPABASE_ANON_KEY` = your **Publishable key** (`sb_publishable_…`)
- `VITE_API_BASE_URL` = http://127.0.0.1:8000

## 3. Create a test login user (one-time)
In the Supabase dashboard → **Authentication → Users → Add user** → "Create new user".
Set an email + password and tick **Auto Confirm User**. (A `profiles` row is
created automatically by the DB trigger.)

To give that user a role for later features, run in the SQL Editor:
```sql
update public.profiles set role = 'admin' where id = '<the-user-uuid>';
```

## 4. Run
```powershell
npm run dev
```
Open http://localhost:5173 → sign in with the test user.

## What you should see
- A login screen with an EN / ગુ toggle (try switching — the whole UI re-renders).
- After login: a sidebar layout and a **Dashboard** with two cards:
  - **System status** → API: Connected, Database: Connected.
  - **Your account** → your email and role.
- The green "all connected" note confirms React → FastAPI → Supabase works end-to-end.

> Note: `role` shows "Not assigned" until you set `app_metadata.role` for the
> user (we wire role-into-token in a later day). It does not block login.

## Project layout
```
frontend/
  index.html               # loads Inter + Noto Sans Gujarati fonts
  src/
    main.jsx               # app bootstrap (router + auth provider)
    App.jsx                # routes
    index.css              # design system / styles
    lib/
      supabase.js          # Supabase client
      api.js               # fetch helper (attaches Bearer token)
    contexts/AuthContext.jsx
    i18n/                  # en.json, gu.json, init
    components/            # Layout, LanguageToggle, ProtectedRoute
    pages/                 # Login, Dashboard
```
