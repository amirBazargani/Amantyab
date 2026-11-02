# PHASE 1 — apps, process design, models   (due 2026-11-04)
PDF scope: define apps · design app/web processes · design and define models.
Rule: do NOT write views/urls/templates/forms in this phase.

- [x] **P1-01 Repo and environment**
  - Goal: working Django project on PostgreSQL, pushed to GitHub.
  - Files: `backend/` (Django project named `config`), `backend/requirements.txt`, `backend/.env.example`, `.gitignore`, `docker-compose.yml`, `README.md`.
  - Steps: create venv; install Django, psycopg[binary], python-dotenv, Pillow; `django-admin startproject config backend`; settings read env (SECRET_KEY, DEBUG, DB_NAME/USER/PASSWORD/HOST/PORT); LANGUAGE_CODE='fa', TIME_ZONE='Asia/Tehran', USE_TZ=True; MEDIA/STATIC config; `docker compose up -d` Postgres; first commit; add GitHub remote; push `main`.
  - Acceptance: `python manage.py check` OK; `python manage.py migrate` runs on PostgreSQL; `.env` is git-ignored; repo visible on GitHub.
  - Commits: `chore: initialize Django project with PostgreSQL settings` · `chore: add docker-compose, env example and gitignore`
  - Done notes: Django 6.1 config project initialized; PostgreSQL 16 running via Docker Compose; psycopg 3 and python-dotenv configured; fa/Asia/Tehran set; static and media configured; .env git-ignored; verified via check and migrate.

- [x] **P1-02 Create apps + custom user setting**
  - Goal: apps exist and are installed; `AUTH_USER_MODEL` set BEFORE any migrate.
  - Files: `backend/accounts|catalog|rentals|reviews|chat|core/` (startapp), `backend/config/settings.py`.
  - Acceptance: `check` OK; all six apps in INSTALLED_APPS; `AUTH_USER_MODEL = "accounts.User"`. (If `migrate` was already run in P1-01, drop and recreate the dev DB.)
  - Commit: `chore: create accounts, catalog, rentals, reviews, chat, core apps`
  - Done notes: Created 6 apps (accounts, catalog, rentals, reviews, chat, core); added to INSTALLED_APPS; set AUTH_USER_MODEL = "accounts.User"; defined base User model; dropped and recreated dev PostgreSQL DB for clean slate; verified with manage.py check (0 issues).

- [x] **P1-03 Process design documents**
  - Goal: finalise diagrams and write the per-app/web process descriptions (Persian).
  - Files: `docs/PROCESSES.md`, `docs/REPORT.md` (sections 1 and 2 only).
  - Acceptance: 4 mermaid diagrams render on GitHub (whole site, rental state machine, search→rent, dispute); REPORT §2 has a paragraph for web + each of the 6 apps. Also export the main diagram as PNG into `docs/img/` if a tool is available (optional).
  - Commit: `docs: add process diagrams and process descriptions`
  - Done notes: Finalised 4 Mermaid diagrams in docs/PROCESSES.md and docs/REPORT.md §1 (whole site, rental state machine, search-to-rent, dispute resolution); wrote detailed Persian process descriptions for web and each of the 6 apps in docs/REPORT.md §2; verified mermaid syntax and Django system check.

- [x] **P1-04 accounts models**
  - Files: `backend/accounts/models.py`, `admin.py`, migration.
  - Goal: `User` exactly as in docs/DOMAIN.md.
  - Acceptance: `makemigrations` creates 0001; `migrate` OK; `createsuperuser` works.
  - Commit: `feat(accounts): add custom User model`
  - Done notes: Implemented custom User model extending AbstractUser with unique email, phone, city, neighborhood, bio, and is_email_verified; configured custom UserAdmin with fieldsets, list_display, search_fields and filters; generated and applied 0001_initial migration on PostgreSQL; verified via check, migrate, and shell createsuperuser tests.

- [x] **P1-05 catalog models**
  - Files: `backend/catalog/models.py`, `admin.py`, migration.
  - Goal: Category, Item, ItemImage with constraints/indexes from DOMAIN.md; `__str__` on all; `Meta.ordering`.
  - Acceptance: migrate OK; in `manage.py shell` create a Category + Item; violating `daily_price=0` raises IntegrityError.
  - Commit: `feat(catalog): add Category, Item and ItemImage models`
  - Done notes: Defined Category (recursive self-parent, unique slug), Item (owner, protected category, condition choices, money fields, delivery options), and ItemImage (order, primary flag); added database CheckConstraints for daily_price > 0 and (allow_pickup or allow_courier); added composite index on (city, is_active); registered CategoryAdmin, ItemAdmin with ItemImageInline, and ItemImageAdmin in admin; created and applied 0001_initial migration; verified constraints in shell.

- [x] **P1-06 rentals models**
  - Files: `backend/rentals/models.py`, `admin.py`, migration.
  - Goal: Rental (status choices, constraints, clean()), Payment, Dispute. NO services/pricing yet (Phase 2).
  - Acceptance: migrate OK; shell: creating Rental with end<start fails; clean() rejects renter==owner.
  - Commit: `feat(rentals): add Rental, Payment and Dispute models`
  - Done notes: Implemented Rental (status and delivery method choices, money fields, tracking code, rental_end_after_start CheckConstraint, clean() validating owner!=renter and overlap prevention against non-cancelled rentals), Payment (receipt_no, kind, status, amount), and Dispute (reason, status, deposit_decision, resolution tracking); configured RentalAdmin with PaymentInline and DisputeInline, PaymentAdmin, and DisputeAdmin; generated and applied 0001_initial migration on PostgreSQL; verified constraints, clean() validations, and payment/dispute creation in shell.

- [x] **P1-07 reviews and chat models**
  - Files: `backend/reviews/models.py`, `backend/chat/models.py`, both `admin.py`, migrations.
  - Acceptance: migrate OK; duplicate (rental, reviewer) review raises IntegrityError; rating 6 raises IntegrityError.
  - Commits: `feat(reviews): add Review model` · `feat(chat): add Conversation and Message models`
  - Done notes: Implemented Review model (rental, reviewer, reviewee, reviewee_role, rating with 1-5 CheckConstraint, duplicate prevention UniqueConstraint, clean() validating completed status and parties); implemented Conversation (item, renter, unique constraint, owner property, clean() self-chat check) and Message (conversation, sender, body, is_read, sender membership clean()); configured ReviewAdmin, ConversationAdmin with MessageInline, and MessageAdmin; created and applied 0001_initial migrations on PostgreSQL; verified constraints and clean validations in shell.

- [ ] **P1-08 Phase 1 wrap-up**
  - Goal: everything registered in admin, docs match code, phase gate.
  - Files: all `admin.py` (list_display, list_filter, search_fields), `docs/DOMAIN.md` (fix any drift from code), `docs/REPORT.md` §3 (models table).
  - Then run `/phase-review`.
  - Commits: `feat: register models in admin` · `docs: fill models section of the report` · `chore: add database backup for phase 1`

### Phase 1 deliverables checklist
- [ ] GitHub repo with all commits; link emailed to instructor the day before
- [ ] 6 apps, models migrated on PostgreSQL
- [ ] Process diagrams + descriptions
- [ ] `db_backup/phase-1.sql` committed; tag `phase-1-done`
