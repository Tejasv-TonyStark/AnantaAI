# Sudarshan: Secure AI Gateway

The demo company is **Sankalpa.AI**, with **Tejasv** as its administrator and twelve
employees. Sudarshan remains the authentication and authorization backend.

Sudarshan is Project 1 of AnantaAI: a small backend that authenticates employees,
checks their permissions before allowing access to future AI agents, and records
security events. The four agent endpoints are intentionally placeholders; the
authentication, authorization, PostgreSQL storage, and Redis limit are real.

## Architecture

```text
Swagger -> FastAPI -> PostgreSQL (users, audit_logs)
                  -> Redis (login attempt counters)

Login -> Argon2 verification -> JWT -> current employee -> permission -> allow/deny -> audit
```

Python 3.12 in Docker, FastAPI/Pydantic, SQLAlchemy 2, PostgreSQL 17,
PyJWT, pwdlib/Argon2, Redis 7, Pytest, and Docker Compose.
The local .venv uses the machine's Python 3.14.

## Run

Docker Desktop must be running. This workspace already has a configured .env.

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f sudarshan-api
```

Open http://localhost:8000 for the access console, http://localhost:8000/docs for
Swagger, or http://localhost:8000/health for service health.

Python renders the frontend with Jinja2 templates in app/templates. CSS and a
small JavaScript interaction layer live in app/static. app/api/web.py serves the
protected HTML views; the JSON API remains available through Swagger.
Select a demo employee and sign in. Overview opens the four prototype applications;
People provides the administrator's employee directory with search and role filters;
People also lets administrators create employees, change roles, and activate or
deactivate accounts. Administrator accounts cannot be demoted or deactivated here.
Activity displays employee names and readable messages with employee-ID, search,
and inclusive UTC date filters. Filtering happens in PostgreSQL before pagination.
My account displays the current identity, Python-derived permissions and reasons,
and a change-password form requiring the current password.
Public registration is closed. POST /auth/register remains an admin-only endpoint
for creating employees; POST /admin/users also accepts a role. Changes and their
audit events commit together. JWTs stay in page memory;
refreshing or signing out clears the local token (it does not revoke the JWT on
the server). The interface uses the same API and permissions as Swagger.
The API waits for healthy PostgreSQL and Redis, creates the two tables, and
seeds thirteen demo accounts on startup. Original demo accounts are renamed in
place, preserving their IDs, password hashes, and audit links. Historical records
still describe events performed under the old demo identities. Subsequent seeding
preserves existing roles and passwords. PostgreSQL data persists in a named volume.

```powershell
docker compose down
```

For a fresh checkout, copy .env.example to .env, generate separate random values
for POSTGRES_PASSWORD and JWT_SECRET, and put the same database password in
DATABASE_URL. Generate each value with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

.env is excluded from Git and the Docker image. DATABASE_URL and REDIS_URL use
Compose service names. API_PORT controls the host port. Database and Redis ports
are not published. The API binds to the local machine for this demo.

## Demo Logins

All thirteen demo accounts initially use the public demo password **DemoPass123!**.
After changing a password, type your new password instead of the demo autofill.
DEMO_PASSWORD controls initial seeding; removing it disables demo account creation.
Changing it does not overwrite passwords already stored in PostgreSQL.

| Name | Email | Role |
| --- | --- | --- |
| Tejasv | tejasv@sankalpa.example.com | admin |
| Gautam Rajavarapu | gautam.rajavarapu@sankalpa.example.com | employee |
| T Revanth | t.revanth@sankalpa.example.com | data_analyst |
| G Giridar | g.giridar@sankalpa.example.com | security_engineer |
| Keerthana | keerthana@sankalpa.example.com | employee |
| Sathvika | sathvika@sankalpa.example.com | data_analyst |
| Likith | likith@sankalpa.example.com | security_engineer |
| Ranga | ranga@sankalpa.example.com | employee |
| Vishwa | vishwa@sankalpa.example.com | security_engineer |
| Sai | sai@sankalpa.example.com | employee |
| Srikar Rao | srikar.rao@sankalpa.example.com | data_analyst |
| Nishanth | nishanth@sankalpa.example.com | employee |
| SriKar rao | srikar.rao2@sankalpa.example.com | security_engineer |

The two Srikar entries are distinct accounts as listed in the requested roster.
Addresses use the reserved example.com domain; no real email service is involved.
Roles are assigned once in app/db/seed.py, not randomized on every startup.

In Swagger, execute POST /auth/login with an email and password, copy the returned
access_token, then paste only that token into **Authorize**. Try /users/me and
the agent routes. More than five login attempts from one IP within 60 seconds
returns 429; wait for the Retry-After interval before logging in again.

## API and Permissions

| Method | Path | Required access |
| --- | --- | --- |
| GET | /health | Public; checks PostgreSQL and Redis |
| POST | /auth/register | Public; always creates employee |
| POST | /auth/login | Public; Redis limit |
| GET | /users/me | Active user with valid JWT |
| GET | /admin/users | users.read (admin only) |
| GET | /admin/audit-logs | audit.read |
| POST | /agents/rag/chat | agent.rag.use |
| POST | /agents/sql/query | agent.sql.use |
| POST | /agents/security/investigate | agent.security.use |
| POST | /agents/cloud/analyze | agent.cloud.use |

| Role | RAG | SQL | Security | Cloud | Audit | User list |
| --- | --- | --- | --- | --- | --- | --- |
| employee | Yes | No | No | No | No | No |
| data_analyst | Yes | Yes | No | No | No | No |
| security_engineer | Yes | No | Yes | Yes | Yes | No |
| admin | Yes | Yes | Yes | Yes | Yes | Yes |

Both list endpoints support limit (1-100) and offset. Agent routes need no body.
Registration accepts name, email, and an 8-128 character password. Login accepts
email and password. Unexpected fields, including role, are rejected. Emails are
normalized to lowercase. Response schemas exclude password hashes, and validation
errors do not echo submitted input.

## Design to Explain

- **Database:** users holds id, name, email, hashed_password, role, is_active,
  created_at. audit_logs holds id, user_id, action, resource, status, timestamp.
  One role per user and a Python permission map keep this prototype small.
- **Authentication:** pwdlib hashes passwords with Argon2id. Login verifies the
  hash and issues a signed JWT containing only sub (user ID) and exp (expiry).
  JWTs are signed, not encrypted; no credentials belong in their payloads.
- **Authorization:** get_current_user validates the token and reloads the user
  from PostgreSQL. require_permission checks the current role. A role change or
  deactivation takes effect on the next request, without issuing a new JWT.
  Missing/invalid credentials return 401; insufficient permission returns 403.
- **Audit:** registration, successful/failed login, access grants/denials, and
  authorized agent requests are stored in PostgreSQL. Unknown actors have a null
  user_id. Passwords, tokens, request bodies, and configuration secrets are not
  recorded. Registration and its audit event commit in one transaction.
- **Rate limit:** Redis INCR and EXPIRE NX run in one transaction. The first
  request starts a 60-second window; later attempts do not extend it. The sixth
  attempt returns 429. A Redis failure returns 503 rather than bypassing the limit.
  Forwarded IP headers are disabled for this direct-access local demo.

## Tests

```powershell
docker compose exec sudarshan-api python -m pytest -q -p no:cacheprovider
```

The 53 tests cover health/Swagger, registration and hashing, login, invalid and
expired tokens, inactive accounts, every role/route combination, audit records,
role changes, Redis limiting/reset, Redis failure, and repeatable roster migration
that preserves password hashes and audit links. Tests use real PostgreSQL
and Redis. Each test rolls back its database changes and removes its own Redis
key, preserving demo data. Run the suite serially against the local demo stack.

The existing virtual environment also has the dependencies installed:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The default .env addresses services inside Docker, so run the app/tests in
Compose. Running Python on the host requires reachable database/Redis URLs.

## Scope and Future AnantaAI Integration

Routers define HTTP endpoints; services handle authentication and audit writes;
core contains configuration, hashing/JWT, and permission checks. No repository,
controller, or factory layer is needed for two tables and this workflow.

AnantaAI can later replace each authorized agent response with the corresponding
agent call while retaining the same authentication, permission, and audit checks.
The Docker image can later run on EC2 with environment-supplied database, Redis,
and JWT settings. Nothing has been deployed to AWS.

This is a local prototype: open registration, public demo accounts, no refresh
tokens/logout revocation, and no password reset. Table creation uses create_all,
which does not migrate existing schemas. Future deployment needs migrations,
HTTPS, removal of demo accounts, restricted registration, and an explicit trusted
proxy configuration. Per-IP limits can group users behind the same network and
are not a complete brute-force defense. Audit writes are synchronous; a database
failure fails the request. Two test warnings currently come from upstream
Starlette/httpx and AnyIO deprecations; all tests pass.

Implementation references: [pwdlib](https://frankie567.github.io/pwdlib/reference/pwdlib/),
[PyJWT](https://pyjwt.readthedocs.io/en/latest/usage.html),
[Redis counter pattern](https://redis.io/docs/latest/commands/incr/).
