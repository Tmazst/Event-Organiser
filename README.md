# Umcimby — Event Planner

A simple event-planning web app for Eswatini organizers. The focused MVP lets a user set up an event, build a budget, compare vendor quotations, collaborate with a planning team and preview or download a clear PDF report.

## Current MVP

- Account registration and login
- Basic event setup
- Budget target and live financial summary
- Budget categories
- Multiple vendor quotations per category
- Selected quotation tracking
- Free plan with a configurable four-budget-item limit
- E40 Standard project upgrade through MojaPOS / MTN MoMo
- E30 team-member access with owner-pays or invitee-pays choice
- Private, expiring invitation links and shared project access
- Live budget totals while quotations are added and selected
- Event profile photo with a friendly placeholder
- Account details, active plan and payment history
- Font Awesome-enhanced navigation and actions
- Installable Umcimby PWA with branded app icons and an offline fallback
- Responsive, simple interface
- Downloadable event report with budget and selected quotation details

## Run locally

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
# In .env, use SESSION_COOKIE_SECURE=false for local HTTP development only.
flask --app run db upgrade
pytest -q
flask --app run run --debug
```

Open `http://127.0.0.1:5000`.

Keep `SESSION_COOKIE_SECURE=true` in production, where the application is served
over HTTPS.

## Upgrading an existing installation

Back up the database and uploaded photos, then run:

```bash
flask --app run db upgrade
flask --app run migrate-event-photos
```

The second command moves existing event photos out of the public static folder
and into authenticated storage. Run it once before restarting Gunicorn. It is
safe to rerun if an interrupted deployment needs to be resumed.

## First database migration

The initial Alembic migration is included. For later model changes:

```bash
flask --app run db migrate -m "Describe the change"
flask --app run db upgrade
```

## Deliberately deferred

Programme planning, guest lists, tasks and messaging can be introduced later. The current navigation remains intentionally small so new users can understand the app quickly.

## Pricing configuration

Pricing and free-tier limits are controlled from `.env`:

```ini
FREE_BUDGET_ITEM_LIMIT=4
OWNER_PLAN_PRICE=40.00
STAKEHOLDER_PRICE=30.00
```

Local proofing uses MojaPOS mock mode. Before production, set both mock options to
`false`, add the real API key and configure `/api/payment/callback` in MojaPOS.
