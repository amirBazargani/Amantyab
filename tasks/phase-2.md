# PHASE 2 — views, urls, templates, forms, test data
Rule: server-rendered Django templates (Tailwind CDN, Persian RTL). No React yet. No managers yet (plain ORM in views is OK; Phase 3 refactors it into managers).
Each app has its own `urls.py` with `app_name`; root `config/urls.py` includes them.

- [ ] **P2-01 Base layout**
  - Files: `backend/templates/base.html`, `partials/navbar.html`, `partials/messages.html`, `404.html`, `500.html`, `core/views.py` (home), `core/urls.py`.
  - Acceptance: home page renders RTL with Vazirmatn font, navbar shows login/signup or username/logout, Django messages visible, custom 404 works with DEBUG=False.
  - Commit: `feat(core): add base layout, navbar and home page`

- [ ] **P2-02 accounts: auth + profile**
  - Files: `accounts/forms.py` (SignUpForm, ProfileForm), `views.py` (signup, login, logout, profile edit, public profile), `urls.py`, `templates/accounts/*.html`.
  - Acceptance: sign up → logged in; wrong password shows error; profile edit saves; public profile shows name, city and items; anonymous user is redirected from profile edit to login.
  - Commits: `feat(accounts): add signup and login views` · `feat(accounts): add profile pages`

- [ ] **P2-03 catalog: browse + detail**
  - Files: `catalog/views.py` (item_list with GET filters q, category, city, max_price; item_detail), `urls.py`, templates, `partials/item_card.html`.
  - Acceptance: filters combine correctly; inactive items are hidden; detail shows images, prices, deposit, owner, delivery options.
  - Commit: `feat(catalog): add item list with filters and detail page`

- [ ] **P2-04 catalog: owner management**
  - Files: `catalog/forms.py` (ItemForm, ItemImageFormSet), views (my_items, item_create, item_edit, item_toggle_active, item_delete), templates.
  - Acceptance: only the owner can edit/delete (others get 403); image upload works; item with rentals cannot be deleted (show message, suggest pause).
  - Commits: `feat(catalog): add ItemForm and image formset` · `feat(catalog): add owner item management views`

- [ ] **P2-05 rentals: request, price, payment, receipt**
  - Files: `rentals/services.py` (calculate_price, has_overlap, create_rental, simulate_payment), `forms.py` (RentalRequestForm with clean() for dates/overlap/own item), views (rental_request, rental_pay, rental_receipt), templates.
  - Acceptance: price matches the rule in DOMAIN.md (test hour and day cases by hand); overlap rejected; owner cannot rent own item; payment creates Payment rows (rent, deposit), status → confirmed, tracking_code set.
  - Commits: `feat(rentals): add pricing and overlap services` · `feat(rentals): add rental request form and views` · `feat(rentals): add simulated payment and receipt`

- [ ] **P2-06 rentals: lifecycle**
  - Files: `rentals/services.py` (transition functions with allowed-transition table), views (my_rentals, owner_rentals, rental_detail, handover, mark_returned, confirm_return, cancel), templates.
  - Acceptance: illegal transitions are impossible (button hidden + server refuses); confirm_return creates deposit_refund + payout Payment rows and sets completed; cancel rules as in DOMAIN.md.
  - Commit: `feat(rentals): add rental lifecycle actions`

- [ ] **P2-07 reviews + chat**
  - Files: `reviews/forms.py`, views (review_create), templates; `chat/forms.py`, views (start/open conversation, send message, inbox), templates.
  - Acceptance: review only after completed, once per side; averages appear on profile and item page; messages show in order; only the 2 participants can open a conversation.
  - Commits: `feat(reviews): add two-way review form and views` · `feat(chat): add conversations and messages`

- [ ] **P2-08 disputes + admin dashboard**
  - Files: `rentals/forms.py` (DisputeForm, DisputeResolveForm), views (dispute_open, admin_dispute_list, admin_dispute_resolve, admin_dashboard), templates. Staff-only checks.
  - Acceptance: participant can open a dispute on handed_over/returned; non-staff get 403 on admin pages; resolving sets deposit decision, creates the matching Payment row and completes the rental; dashboard shows counts (users, items, rentals by status, total commission).
  - Commit: `feat(rentals): add disputes and admin dashboard`

- [ ] **P2-09 Test data entry**
  - Files: `core/management/commands/seed_demo.py`.
  - Goal: idempotent command: 1 admin, 8 users, 6 categories, 25 items (with city/neighborhood variety), rentals in EVERY status, reviews, 2 conversations, 1 open and 1 resolved dispute. Print the credentials. Placeholder images generated with Pillow.
  - Acceptance: running it twice does not duplicate; every page of the site has data to show.
  - Commit: `feat(core): add seed_demo management command`

- [ ] **P2-10 Phase 2 wrap-up**
  - Files: `docs/REPORT.md` §5 (views table), `docs/DEFENSE.md`, `docs/QA-P2.md` (manual checklist: one line per page/action).
  - Then `/phase-review`.

### Phase 2 deliverables checklist
- [ ] every app has urls + views + templates + forms as listed
- [ ] seed_demo works on an empty DB
- [ ] QA checklist all ticked; `db_backup/phase-2.sql`; tag `phase-2-done`
