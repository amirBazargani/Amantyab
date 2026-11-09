# PHASE 2 — views, urls, templates, forms, test data
Rule: server-rendered Django templates (Tailwind CDN, Persian RTL). No React yet. No managers yet (plain ORM in views is OK; Phase 3 refactors it into managers).
Each app has its own `urls.py` with `app_name`; root `config/urls.py` includes them.

- [x] **P2-01 Base layout**
  - Files: `backend/templates/base.html`, `partials/navbar.html`, `partials/messages.html`, `404.html`, `500.html`, `core/views.py` (home), `core/urls.py`.
  - Acceptance: home page renders RTL with Vazirmatn font, navbar shows login/signup or username/logout, Django messages visible, custom 404 works with DEBUG=False.
  - Commit: `feat(core): add base layout, navbar and home page`
  - Done notes: Created base.html with RTL, Vazirmatn font CDN, and Tailwind CSS; created responsive navbar.html with auth state switches and mobile menu; added messages.html partial supporting Django message levels; added custom 404 and 500 error templates; implemented home view in core/views.py with core/home.html and registered core.urls into config/urls.py; verified via manage.py check (0 issues) and automated test suite verifying status 200, RTL, font, guest/auth/staff navbar states, alert messages, and 404 behavior with DEBUG=False.

- [x] **P2-01A Notification foundation (email + SMS)**
  - Files: `core/models.py` (NotificationLog per DOMAIN), `core/sms.py`, `core/notifications.py`, `core/admin.py`, `templates/notifications/<event>_subject.txt` and `<event>_body.txt` for the 3 events (Persian text, short), `config/settings.py` (EMAIL_BACKEND from env default console, DEFAULT_FROM_EMAIL, `SMS_BACKEND` default `console`), migration.
  - Goal: `notify(user, event, context=None, *, item=None, rental=None)` renders the event templates, sends email (Django `send_mail`) and SMS (backend from `get_sms_backend()`), writes one NotificationLog row per channel (`sent` / `failed` / `skipped` when user has no email or phone). Exceptions are caught, stored in `error`, never re-raised. Backends: `ConsoleBackend` (prints), `LocmemBackend` (list `sms.outbox`).
  - Acceptance: in `manage.py shell`, `notify(user, "signup_confirmation")` prints the email and SMS in the console and creates 2 log rows; a user without phone gets an sms row with status `skipped`; a backend that raises produces a `failed` row and no exception; rows visible in admin.
  - Commits: `feat(core): add NotificationLog model` · `feat(core): add SMS backends and notify service`
  - Done notes: Defined NotificationLog model in core/models.py with index (event, created_at) and SET_NULL FKs; generated and applied migration core.0001_initial; registered model in admin with readonly fields and filters; added email/SMS settings in config/settings.py; implemented swappable SMS backends in core/sms.py (ConsoleBackend, LocmemBackend, get_sms_backend); created Persian event templates in templates/notifications/; implemented notify() service with dual-channel sending, sent/skipped/failed statuses, and safe exception handling; verified via manage.py check and automated shell tests covering all 4 acceptance criteria.

- [x] **P2-02 accounts: auth + profile**
  - Files: `accounts/forms.py` (SignUpForm, ProfileForm), `views.py` (signup, login, logout, profile edit, public profile), `urls.py`, `templates/accounts/*.html`.
  - Acceptance: sign up → logged in; wrong password shows error; profile edit saves; public profile shows name, city and items; anonymous user is redirected from profile edit to login.
  - Commits: `feat(accounts): add signup and login views` · `feat(accounts): add profile pages`
  - Done notes: Implemented SignUpForm (UserCreationForm subclass), LoginForm (AuthenticationForm subclass with Persian errors) and ProfileForm (ModelForm with Tailwind styling); created signup, login, logout, profile edit and public profile views; routed URLs under accounts app and registered in config/urls.py; added Persian RTL templates for signup, login, profile edit and public profile showing active items; verified all 5 acceptance criteria with automated tests and shell Client.

- [x] **P2-02A Signup confirmation by email and SMS**
  - Files: `accounts/forms.py` (phone required + validator `^09\d{9}$` + normalisation in SignUpForm and ProfileForm), `accounts/views.py` (call `notify(user, "signup_confirmation")` after successful signup), templates (phone field).
  - Acceptance: signup without/invalid phone shows a Persian error; valid signup → logged in, console shows confirmation email AND SMS, 2 NotificationLog rows; a notification failure (simulate by raising in backend) does not stop signup.
  - Commit: `feat(accounts): require phone and send signup confirmation`
  - Done notes: Required Iranian mobile phone (09 + 9 digits) with normalisation (Persian/Arabic digits, prefixes) in SignUpForm and ProfileForm; connected notify() service in signup view to trigger email and SMS notifications; updated templates with required asterisk and format hint; verified with 12 automated unit tests and shell QA covering missing phone error, invalid format error, Persian digit normalization, dual NotificationLog rows creation, and simulated SMS backend failure fault tolerance.

- [x] **P2-03 catalog: browse + detail**
  - Files: `catalog/views.py` (item_list with GET filters q, category, city, max_price; item_detail), `urls.py`, templates, `partials/item_card.html`.
  - Acceptance: filters combine correctly; inactive items are hidden; detail shows images, prices, deposit, owner, delivery options.
  - Commit: `feat(catalog): add item list with filters and detail page`
  - Done notes: Implemented item_list view with multi-parameter GET filters (q, category by slug/id, city, and max_price), item_detail view with access control hiding inactive items from general public (404) while allowing owner/staff access; created partials/item_card.html, catalog/item_list.html with search/filters/chips, and catalog/item_detail.html with image gallery, specs, deposit explanation, owner profile link and delivery badges; registered routes in catalog/urls.py and mounted in config/urls.py; verified with 8 comprehensive automated unit tests in catalog/tests.py and shell client verification covering all 3 acceptance criteria.

- [x] **P2-03A Geo fields migration (instructor change)**
  - Files: `catalog/models.py`, `rentals/models.py`, both `admin.py`, NEW migrations only (never edit old migrations).
  - Goal: add the fields from DOMAIN.md: Item latitude/longitude/address_text; Rental delivery_address/delivery_latitude/delivery_longitude/reminder_sent_at; constraints and validators.
  - Acceptance: `makemigrations` creates one new migration per app; `migrate` OK on the existing database with existing rows; shell: lat without lng raises IntegrityError; latitude 120 fails `full_clean()`.
  - Commit: `feat(catalog): add pickup location fields` · `feat(rentals): add delivery location and reminder fields`
  - Done notes: Added latitude (Decimal 9,6), longitude (Decimal 9,6), and address_text to Item model with validators and CheckConstraint item_lat_lng_both_or_neither; added delivery_address, delivery_latitude, delivery_longitude, and reminder_sent_at to Rental model with validators and CheckConstraint rental_delivery_lat_lng_both_or_neither; organized admin fieldsets for both ItemAdmin and RentalAdmin; created new migrations catalog.0002 and rentals.0002 and applied them successfully to existing database; verified via manage.py check (0 issues), 26 unit tests, and shell client QA confirming IntegrityError on partial coordinates and ValidationError on out-of-range latitude.

- [x] **P2-04 catalog: owner management**
  - Files: `catalog/forms.py` (ItemForm, ItemImageFormSet), views (my_items, item_create, item_edit, item_toggle_active, item_delete), templates.
  - Acceptance: only the owner can edit/delete (others get 403); image upload works; item with rentals cannot be deleted (show message, suggest pause).
  - Commits: `feat(catalog): add ItemForm and image formset` · `feat(catalog): add owner item management views`
  - Done notes: Implemented ItemForm with validations and ItemImageFormSet with inline multi-image uploads; implemented my_items owner dashboard displaying active rentals, renter info, and remaining time calculation; implemented item_create, item_edit, item_toggle_active, and item_delete with 403 authorization for non-owners and deletion blockage on rented items; verified via 37 unit tests and live shell QA.

- [x] **P2-04A Map: choose and show item location**
  - Files: `templates/partials/map_picker.html`, `templates/partials/map_view.html`, `catalog/forms.py` (ItemForm gets latitude, longitude as hidden fields + address_text), item create/edit templates, item detail template.
  - Goal: Leaflet + OSM (CDN). Picker: click or drag a marker, writes the two hidden inputs, default centre = Tehran. Viewer: read-only map with one marker + the address text. ItemForm `clean()`: both coordinates or none, ranges valid.
  - Acceptance: owner sets a point and it persists; item detail shows the map; item without coordinates shows only the address text and no map; invalid coordinates (tampered POST) are rejected by the form.
  - Commits: `feat(core): add Leaflet map picker and viewer partials` · `feat(catalog): add pickup location to item form and detail`
  - Done notes: Created map_picker.html and map_view.html partials using Leaflet 1.9.4 and OpenStreetMap; embedded picker in item_form.html and viewer in item_detail.html; validated coordinates range (-90..90 and -180..180) and both-or-neither constraint in ItemForm.clean(); verified via 27 unit tests and live shell QA.

- [x] **P2-04B Item registration confirmation by email and SMS**
  - Files: `catalog/views.py` (item_create).
  - Goal: after a NEW item is saved call `notify(owner, "item_registered", {"title": item.title}, item=item)`; editing an item does not notify.
  - Acceptance: creating an item prints email + SMS with the title and creates 2 NotificationLog rows linked to the item; edit sends nothing.
  - Commit: `feat(catalog): notify owner when an item is registered`
  - Done notes: Called core.notifications.notify upon successful item creation in item_create view; verified email and SMS console printout and 2 NotificationLog rows linked to item; verified item_edit does not send notifications via 29 catalog unit tests and live shell QA.

- [x] **P2-05 rentals: request, price, payment, receipt**
  - Files: `rentals/services.py` (calculate_price, has_overlap, create_rental, simulate_payment), `forms.py` (RentalRequestForm with clean() for dates/overlap/own item), views (rental_request, rental_pay, rental_receipt), templates.
  - Acceptance: price matches the rule in DOMAIN.md (test hour and day cases by hand); overlap rejected; owner cannot rent own item; payment creates Payment rows (rent, deposit), status → confirmed, tracking_code set.
  - Commits: `feat(rentals): add pricing and overlap services` · `feat(rentals): add rental request form and views` · `feat(rentals): add simulated payment and receipt`
  - Done notes: Implemented calculate_price (hourly/daily ceil), has_overlap, create_rental, and simulate_payment in rentals/services.py; created RentalRequestForm with validation; built views and templates for rental_request, rental_pay, and rental_receipt; verified all acceptance criteria via 25 unit tests and live shell QA.

- [ ] **P2-05A Map for the handover location**
  - Files: `rentals/forms.py` (RentalRequestForm: if delivery_method = courier then delivery_address is required; optional pin via hidden delivery_latitude/longitude), rental request template (map_picker, shown only for courier), receipt and rental_detail templates (map_view).
  - Goal: for `pickup` rentals show the ITEM's pickup point; for `courier` rentals show the renter's delivery point; same partials as P2-04A.
  - Acceptance: courier without address is rejected; receipt shows the right map for each method; no map when no coordinates exist.
  - Commit: `feat(rentals): show handover location on map`
  - Done notes:

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
  - Goal: idempotent command: 1 admin, 8 users, 6 categories, 25 items (with city/neighborhood variety), rentals in EVERY status, reviews, 2 conversations, 1 open and 1 resolved dispute. Print the credentials. Placeholder images generated with Pillow. Also: every user gets a fake phone `0912xxxxxxx`; at least 10 items get coordinates (Tehran, Tabriz, Isfahan neighbourhoods) and address_text; one `handed_over` rental ends in about 2 hours (for the reminder demo) and another ends in 3 days; one courier rental has a delivery point.
  - Acceptance: running it twice does not duplicate; every page of the site has data to show.
  - Commit: `feat(core): add seed_demo management command`

- [ ] **P2-10 Phase 2 wrap-up**
  - Files: `docs/REPORT.md` §5 (views table), `docs/DEFENSE.md`, `docs/QA-P2.md` (manual checklist: one line per page/action).
  - Then `/phase-review`.

### Phase 2 deliverables checklist
- [ ] every app has urls + views + templates + forms as listed
- [ ] seed_demo works on an empty DB
- [ ] signup + item registration send email AND SMS (console) and are visible in NotificationLog
- [ ] maps work on item form, item detail, rental request/receipt
- [ ] QA checklist all ticked; `db_backup/phase-2.sql`; tag `phase-2-done`
