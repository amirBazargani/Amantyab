# PHASE 4 — email verification, tests, template optimisation, report, gap closing
(No bonus items. P4-05 is the stack requirement, do it only after P4-01..P4-04 and P4-06 are done.)

- [ ] **P4-01 Email verification**
  - Files: `accounts/tokens.py` (use `django.core.signing.TimestampSigner` or `default_token_generator`), views (verify_email, resend_verification), templates (`emails/verify.txt`, `verify_sent.html`), settings (EMAIL_BACKEND from env: console in dev, SMTP in prod), `accounts/models.py` (no change; uses is_email_verified).
  - Goal: after signup, a link valid for 24h; unverified users can log in and browse but cannot create items, request rentals, or send messages (decorator `verified_required`).
  - Acceptance: console shows the email; link verifies; expired/tampered link shows a friendly error; resend works; logs record verification events.
  - Commits: `feat(accounts): add email verification tokens and views` · `feat(core): restrict actions to verified users`

- [ ] **P4-02 Tests**
  - Files: `*/tests/` packages (`test_models.py`, `test_forms.py`, `test_views.py`, `test_services.py`), `core/tests/test_cookies.py`.
  - Must cover: model constraints; pricing (hour/day); overlap detection; every legal and illegal rental transition; queryset methods; permission checks (403/redirect); review rules; dispute resolution; email verification; session remember-me; cookie tamper.
  - Acceptance: `python manage.py test` green; at least ~40 tests; a short "how to run tests" in README.
  - Commits (one per app): `test(accounts): ...`, `test(catalog): ...`, `test(rentals): ...`, `test(reviews): ...`, `test(chat): ...`, `test(core): ...`

- [ ] **P4-03 Template optimisation**
  - Goal: remove duplicated markup (partials: item_card, rental_row, form_field, pagination-free list), `{% include %}` with parameters, custom template tags only where they remove repetition; fix N+1 queries with `select_related/prefetch_related` in the QuerySets; add `assertNumQueries` tests for item_list, my_rentals, admin_dashboard; remove inline logic from templates; compress/resize uploaded images on save (Pillow, max 1200px).
  - Acceptance: item_list ≤ 5 queries for 25 items; templates have no repeated card markup; Lighthouse/DevTools shows no blocking errors.
  - Commits: `refactor: extract template partials` · `perf: fix N+1 queries and add query-count tests` · `perf(catalog): resize uploaded images`

- [ ] **P4-04 Complete the report**
  - Files: `docs/REPORT.md` fully filled: §1 diagram image, §2 process texts, §3 models+relations, §4 managers+reasons, §5 views table (generate the list from `urls.py` files), §6 extras. Export `docs/REPORT.pdf` if a tool is available (else the human exports from the md).
  - Acceptance: every PDF-required item (process diagram, web/app processes, models and relations, managers and why, views) is present and matches the code.
  - Commit: `docs: complete final project report`

- [ ] **P4-05 React islands + Tailwind build (stack requirement)**
  - Files: `frontend/` (Vite + React + Tailwind), `backend/templates/base.html` (load built assets via a small `{% vite_asset %}`-free approach: fixed filenames from `vite build` into `backend/static/dist/`), `catalog/views.py` (+ `item_search_json`), `rentals/views.py` (+ `price_preview_json`).
  - Goal: replace Tailwind CDN with the built CSS. Island 1: live item search/filter list (fetch to `item_search_json`). Island 2: booking price preview on the rental request page (fetch to `price_preview_json`, same calculate_price service). Islands mount on `<div id="..." data-*>` elements; pages still work without JS (normal form/GET fallback).
  - Acceptance: `npm run build` OK; both islands work; CSRF cookie header used on POST fetches; tests for both JSON endpoints.
  - Commits: `chore(frontend): scaffold Vite React Tailwind` · `feat(catalog): add live search island and JSON endpoint` · `feat(rentals): add price preview island and endpoint` · `chore: switch base template to built Tailwind assets`

- [ ] **P4-06 Gap-closing pass over phases 1–3**
  - Goal: run the checklist of each earlier phase again; fix what is missing or drifted; fresh-database run (`drop db → migrate → seed_demo → runserver`) must work; update docs.
  - Commit(s): `fix: ...` per gap.

- [ ] **P4-07 Final delivery**
  - `/phase-review`; final `db_backup/phase-4.sql`; README (install, env, run, seed, tests); tag `phase-4-done` and `v1.0`; `docs/DEFENSE.md` complete; a 10-minute demo script in `docs/DEMO.md`.

### Phase 4 deliverables checklist
- [ ] email verification · tests green · optimised templates · full report · earlier phases complete
- [ ] `db_backup/phase-4.sql`; tag `phase-4-done`
