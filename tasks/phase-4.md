# PHASE 4 — email verification, tests, template optimisation, report, gap closing
(No bonus items. P4-05 is the stack requirement, do it only after P4-01..P4-04 and P4-06 are done.)

- [x] **P4-01 Email verification**
  - Files: `accounts/tokens.py` (use `django.core.signing.TimestampSigner` or `default_token_generator`), views (verify_email, resend_verification), templates (`emails/verify.txt`, `verify_sent.html`), settings (EMAIL_BACKEND from env: console in dev, SMTP in prod), `accounts/models.py` (no change; uses is_email_verified).
  - Goal: after signup, a link valid for 24h; unverified users can log in and browse but cannot create items, request rentals, or send messages (decorator `verified_required`). The signup confirmation email from P2-02A gets the verification link added (ONE email, not two); the SMS stays a plain confirmation.
  - Acceptance: console shows the email; link verifies; expired/tampered link shows a friendly error; resend works; logs record verification events.
  - Commits: `feat(accounts): add email verification tokens and views` · `feat(core): restrict actions to verified users`
  - Done notes: TimestampSigner with 24h expiration in accounts/tokens.py; verify_email and resend_verification views in accounts/views.py; templates in templates/accounts/verify_sent.html, templates/emails/verify.txt, templates/notifications/signup_confirmation_email_body.txt; verified_required decorator in core/decorators.py guarding item_create, rental_request, and chat; profile badges and resend button added; 191 automated tests passing.

- [x] **P4-02 Tests**
  - Files: `*/tests/` packages (`test_models.py`, `test_forms.py`, `test_views.py`, `test_services.py`), `core/tests/test_cookies.py`.
  - Must cover: model constraints; pricing (hour/day); overlap detection; every legal and illegal rental transition; queryset methods; permission checks (403/redirect); review rules; dispute resolution; email verification; session remember-me; cookie tamper; notifications (locmem mail outbox + `sms.outbox`: sent, skipped without phone, failed backend does not break the request), phone validation, the reminder command (window, status filter, idempotency), geo validation (both-or-none, ranges, courier requires address).
  - Acceptance: `python manage.py test` green; at least ~40 tests; a short "how to run tests" in README.
  - Commits (one per app): `test(accounts): ...`, `test(catalog): ...`, `test(rentals): ...`, `test(reviews): ...`, `test(chat): ...`, `test(core): ...`
  - Done notes: Monolithic tests.py files modularized into tests/ packages (test_models.py, test_forms.py, test_services.py, test_views.py) across accounts, catalog, rentals, reviews, chat, and core; core/tests/test_cookies.py created with signed cookie tamper resilience tests; notifications tested with locmem outbox and sms.outbox, skipped without phone, resilient against backend failures; reminder command window, status filter, and idempotency verified; geo validation both-or-none, ranges, and courier address requirement verified; 221 automated tests passing 100% green; README updated with running tests guide.

- [x] **P4-03 Template optimisation**
  - Goal: remove duplicated markup (partials: item_card, rental_row, form_field, pagination-free list), `{% include %}` with parameters, custom template tags only where they remove repetition; fix N+1 queries with `select_related/prefetch_related` in the QuerySets; add `assertNumQueries` tests for item_list, my_rentals, admin_dashboard; remove inline logic from templates; compress/resize uploaded images on save (Pillow, max 1200px).
  - Acceptance: item_list ≤ 5 queries for 25 items; templates have no repeated card markup; Lighthouse/DevTools shows no blocking errors.
  - Commits: `refactor: extract template partials` · `perf: fix N+1 queries and add query-count tests` · `perf(catalog): resize uploaded images`
  - Done notes: Extracted reusable template partials (form_field.html, empty_state.html, rental_row.html, item_card.html) removing >500 lines of duplicate markup across catalog, rentals, accounts, and reviews; resolved N+1 queries via select_related and prefetch_related, primary_image property utilizing cached prefetch objects, and values().annotate(Count()) aggregation in admin_dashboard; added assertNumQueries tests for item_list (4 queries for 25 items with images <= 5), my_rentals, and admin_dashboard; implemented Pillow-based automatic image resizing and JPEG/PNG compression in ItemImage.save() with max dimension 1200px guarded by _committed; 227 tests passing green.

- [x] **P4-04 Complete the report**
  - Files: `docs/REPORT.md` fully filled: §1 diagram image, §2 process texts, §3 models+relations, §4 managers+reasons, §5 views table (generate the list from `urls.py` files), §6 extras. Export `docs/REPORT.pdf` if a tool is available (else the human exports from the md). REPORT gets a short "نوتیفیکیشن‌ها و نقشه" part (events, channels, backends, Leaflet/OSM).
  - Acceptance: every PDF-required item (process diagram, web/app processes, models and relations, managers and why, views) is present and matches the code.
  - Commit: `docs: complete final project report`
  - Done notes: Completed docs/REPORT.md matching all Phase 4 features: 5 Mermaid process diagrams (whole flow, rental state machine, search-to-rent, dispute resolution, email verification); full app processes; 11 model specifications and ER diagram with geo fields (latitude, longitude, address_text), reminder_sent_at, delivery_address, and core.NotificationLog; managers and reasons table with chainability; complete 32 views table from urls.py including verify_email and resend_verification; comprehensive extras covering notifications (events, channels, backends, resilience), interactive map (Leaflet/OSM, privacy circle), email verification (TimestampSigner, 24h, verified_required), template optimization, sessions, cookies, logging, 227 tests summary, and PDF export guide; 227 tests passing.

- [x] **P4-05 React islands + Tailwind build (stack requirement)**
  - Files: `frontend/` (Vite + React + Tailwind), `backend/templates/base.html` (load built assets via a small `{% vite_asset %}`-free approach: fixed filenames from `vite build` into `backend/static/dist/`), `catalog/views.py` (+ `item_search_json`), `rentals/views.py` (+ `price_preview_json`).
  - Goal: replace Tailwind CDN with the built CSS. Island 1: live item search/filter list (fetch to `item_search_json`). Island 2: booking price preview on the rental request page (fetch to `price_preview_json`, same calculate_price service). Islands mount on `<div id="..." data-*>` elements; pages still work without JS (normal form/GET fallback).
  - Acceptance: `npm run build` OK; both islands work; CSRF cookie header used on POST fetches; tests for both JSON endpoints.
  - Commits: `chore(frontend): scaffold Vite React Tailwind` · `feat(catalog): add live search island and JSON endpoint` · `feat(rentals): add price preview island and endpoint` · `chore: switch base template to built Tailwind assets`
  - Done notes: Scaffolded frontend/ with Vite 6, React 18, and Tailwind CSS compiling to backend/static/dist/bundle.js and bundle.css; removed Tailwind CDN from base.html; implemented item_search_json view in catalog/views.py and ItemSearchIsland React component with live debounced search and server-rendered fallback; implemented price_preview_json view in rentals/views.py and PricePreviewIsland React component syncing with datetime inputs and sending X-CSRFToken headers on POST; verified full test suite with 237 passing tests.

- [x] **P4-06 Gap-closing pass over phases 1–3**
  - Goal: run the checklist of each earlier phase again; fix what is missing or drifted; fresh-database run (`drop db → migrate → seed_demo → runserver`) must work; update docs.
  - Commit(s): `fix: ...` per gap.
  - Done notes: Fixed seed_demo.py to explicitly assign is_email_verified = True for admin and demo users guaranteeing idempotent setup; verified complete clean database lifecycle (migrate applying 25 migrations cleanly, seed_demo populating 23 users, 9 categories, 32 items, 17 rentals, 25 payments, 9 reviews, 5 conversations, 2 disputes); updated docs/REPORT.md adding Phase 4 JSON endpoints (item_search_json, price_preview_json) bringing total views table to 35, documented React Islands and built Tailwind assets in section 6-7, and updated test suite count to 237; updated docs/QA-P2.md demo usernames; updated README.md with Quickstart setup and Vite compile instructions; verified all 237 tests passing green.

- [ ] **P4-06A (optional) Real SMS gateway adapter**
  - Do ONLY if the human has a Kavenegar account/API key. Files: `core/sms.py` (KavenegarBackend using `urllib.request`, no new package), `.env.example` (`SMS_BACKEND`, `KAVENEGAR_API_KEY`, `KAVENEGAR_SENDER`).
  - Acceptance: with `SMS_BACKEND=kavenegar` a signup sends a real SMS; with the default `console` nothing changes; the key never appears in logs or git. Check the request format against the provider's current docs before coding.
  - Commit: `feat(core): add optional Kavenegar SMS backend`
  - Done notes:

- [ ] **P4-07 Final delivery**
  - `/phase-review`; final `db_backup/phase-4.sql`; README (install, env, run, seed, tests); tag `phase-4-done` and `v1.0`; `docs/DEFENSE.md` complete; a 10-minute demo script in `docs/DEMO.md`.

### Phase 4 deliverables checklist
- [ ] email verification · tests green · optimised templates · full report · earlier phases complete
- [ ] notifications tested; reminder command tested
- [ ] `db_backup/phase-4.sql`; tag `phase-4-done`
