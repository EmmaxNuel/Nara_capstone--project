# NARA — Savings Circle Platform

Nigerian fintech backend that formalises traditional Ajo/Esusu savings culture. Connects salary earners into structured savings circles — members contribute a fixed amount monthly, one member collects the full pot each month, and rotation continues until everyone has collected.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Django 4.2 + Django REST Framework 3.15 |
| Database | MySQL (utf8mb4) |
| Auth | JWT (simplejwt) + OTP via Termii SMS |
| Tasks | Celery + Redis (dev: `CELERY_TASK_ALWAYS_EAGER=True`) |
| Payments | Flutterwave (direct debit / transfers) |
| Notifications | Termii (SMS / WhatsApp), In-app notifications |
| Docs | `NARA_DOCS.md` (full internal reference, 855 lines) |

## Domain Models

| Model | App | Key Fields |
|-------|-----|------------|
| `Member` | `members` | email, phone, BVN, NIN, savings_goal, contribution_tier, status |
| `SavingsGroup` | `groups` | goal_type, contribution_tier, max_members, cycle, reserve_fund |
| `GroupMembership` | `groups` | member, group, rotation_position, has_collected |
| `Contribution` | `contributions` | member, group, amount, month_year, status, method |
| `StandingOrder` | `standing_orders` | member, bank_name, account_number, amount, deduction_day |
| `PotDisbursement` | `disbursements` | group, recipient, amount, month_year, status |
| `InsuranceCover` | `insurance` | member, coverage_amount, claim_reason, grace_period |
| `Waitlist` | `waitlist` | member, goal_type, contribution_tier, priority |
| `Notification` | `notifications` | recipient, type, channel (in-app/SMS/WhatsApp) |
| `AuditLog` | `admin_panel` | member, action, amount, description, ip_address |

## API Endpoints

All endpoints are prefixed with `/api/v1/`. Most require `Authorization: Bearer <access_token>`.

### Authentication (`/api/v1/auth/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `register/` | No | Create account + send OTP |
| POST | `verify-otp/` | No | Verify OTP → activate account + return JWT |
| POST | `login/` | No | Email + password → JWT |
| POST | `refresh/` | No | Refresh token → new access token |
| POST | `logout/` | Yes | Blacklist refresh token |
| POST | `forgot-password/` | No | Send password reset email |
| POST | `reset-password/` | No | Confirm reset with token |

### Onboarding (`/api/v1/onboarding/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `goal/` | Yes | Set savings goal |
| POST | `tier/` | Yes | Set contribution tier |
| GET | `match/` | Yes | Find matching group or join waitlist |
| POST | `confirm/` | Yes | Confirm group join → create standing order + insurance |

### Members (`/api/v1/members/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `me/` | Yes | Get profile |
| PATCH | `me/` | Yes | Update profile |
| GET | `me/dashboard/` | Yes | Dashboard stats (group, contributions, next payout) |
| GET | `me/notifications/` | Yes | List notifications |
| PATCH | `me/notifications/read/` | Yes | Mark all as read |

### Groups (`/api/v1/groups/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `` | Yes | List all FORMING groups |
| GET | `my-group/` | Yes | Current member's group |
| GET | `my-group/members/` | Yes | Group members list |
| GET | `<uuid:group_id>/` | Yes | Group detail by ID |

### Contributions (`/api/v1/contributions/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `` | Yes | List member's contributions |
| POST | `manual/` | Yes | Record manual contribution |
| GET | `statement/` | Yes | PDF contribution statement |
| GET | `<str:month_year>/` | Yes | Detail for specific month |

### Standing Orders (`/api/v1/standing-orders/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `` | Yes | Create standing order |
| GET | `me/` | Yes | Get my standing order |
| PATCH | `me/pause/` | Yes | Pause standing order |
| PATCH | `me/resume/` | Yes | Resume standing order |

### Disbursements (`/api/v1/disbursements/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `` | Yes | List disbursements |
| POST | `process/` | Yes | Trigger monthly pot disbursement |

### Insurance (`/api/v1/insurance/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `me/` | Yes | Get insurance cover details |
| POST | `claim/` | Yes | File an insurance claim |
| GET | `claim/status/` | Yes | Check claim status |

### Waitlist (`/api/v1/waitlist/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `` | Yes | Join waitlist |
| DELETE | `` | Yes | Leave waitlist |
| GET | `position/` | Yes | Check queue position |

### Notifications (`/api/v1/notifications/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `push-token/` | Yes | Register device push token |

## Setup

```bash
# 1. Virtual environment
python -m venv venv && source venv/bin/activate

# 2. Dependencies
pip install -r requirements.txt

# 3. Database (MySQL)
mysql -u root -p -e "CREATE DATABASE nara_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 4. Environment
cp .env.example .env   # fill in DB_PASSWORD, leave API keys blank for dev

# 5. Migrate + seed
python manage.py migrate
python manage.py createsuperuser

# 6. Run
python manage.py runserver
```

## Tests

```bash
python manage.py test          # all 44 tests
python manage.py test apps.authentication   # auth tests only (9)
```

39/44 tests pass. 5 failures are pre-existing — they require live Termii/Flutterwave API keys (external 401 errors on SMS/transfers).

## Background Tasks (Celery)

| Task | Schedule | Description |
|------|----------|-------------|
| `process_monthly_deductions` | 25th, 6am | Debit all standing orders via Flutterwave |
| `check_failed_deductions` | Daily, 9am | Retry/suspend failed deductions |
| `trigger_pot_disbursement` | Last day, 5pm | Send pot to monthly collector |
| `send_deduction_reminders` | Daily, 8am | 3-day reminder before deduction |
| `check_grace_periods` | Daily, 8:30am | Promote waitlist after 60-day grace |
| `promote_waitlist_member` | On slot open | Highest-priority waitlist → group |

## Deployment (Render)

Configure in Render dashboard:

- **Build:** `pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput`
- **Web:** `gunicorn config.wsgi:application --workers 2 --bind 0.0.0.0:$PORT`
- **Worker:** `celery -A config worker --loglevel=info`
- **Beat:** `celery -A config beat --loglevel=info`

Set env vars: `SECRET_KEY`, `DEBUG=False`, `DJANGO_SETTINGS_MODULE=config.settings.prod`, database credentials, `REDIS_URL`, Flutterwave keys, Termii keys.

---

*See `NARA_DOCS.md` for the full 855-line developer reference covering every model, view, utility, security control, and design decision.*
