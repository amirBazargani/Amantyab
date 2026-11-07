# UPDATE-01 — instructor change request
Instructor asked for:
1. Reminder before a rental period ends, by EMAIL and SMS.
2. Show the handover (pickup/delivery) location on a MAP.
3. Confirmation of signup and of item registration by SMS, and ALSO by EMAIL — email versions become CORE features.
These override the old "no bonus items" rule for exactly these features. Everything else stays out of scope.

Apply sections 1–8 with `/apply-update UPDATE-01`.

---
## 1. AGENTS.md — REPLACE one line
Find the line starting with `- Never invent features (no bonus items:` and replace the whole line with:
`- Never invent features. The only extras allowed are those in docs/DECISIONS.md D-06: email + SMS notifications, map, React islands (P4-05). Still excluded: SMS-based account verification, Permission extras, Pagination, per-role dashboards other than admin, any other bonus item.`

## 2. .agent/rules/01-project-context.md — APPEND at end
- Notifications (email AND SMS): signup confirmation, item registration confirmation, rental-ending reminder. Sending goes through `core/notifications.py`; a failed send must never break the request. Map (Leaflet + OpenStreetMap) shows pickup/delivery location. See DECISIONS D-06, D-09..D-12.

## 3. docs/DECISIONS.md — REPLACE row D-06, APPEND rows D-09..D-12
Replace the whole D-06 row with:
| D-06 | Instructor change request 1 puts these in scope: email AND SMS for signup confirmation, item-registration confirmation and rental-ending reminder; map showing pickup/delivery location. Still excluded: SMS account verification, Permission extras, Pagination, other bonus items. React islands (P4-05) remain a stack requirement. | instructor requirement | final |
Append after the last row of the table:
| D-09 | SMS goes through `core/sms.py` with swappable backends: `console` (default; prints + logs), `locmem` (tests; `sms.outbox`), optional real `kavenegar` (P4-04A, stdlib urllib, needs API key). Every send attempt (email or SMS) is stored in `core.NotificationLog`. A failed send is logged and never breaks the user's request. | no real gateway needed for the demo; real one is a config switch | final |
| D-10 | Map = Leaflet 1.9 + OpenStreetMap tiles from CDN, no API key. Vanilla JS in template partials `partials/map_picker.html` and `partials/map_view.html`. Owner picks the item's pickup point by clicking the map; renter may pin a courier delivery point. Needs internet; address text is the fallback. | simplest, explainable | final |
| D-11 | Rental-ending reminder = management command `send_rental_reminders` (no Celery). Window setting `RENTAL_REMINDER_HOURS` (default 3). Idempotent via `Rental.reminder_sent_at`. Scheduled by cron / Windows Task Scheduler, or run with `--loop`. | one developer, no extra infra | final |
| D-12 | Phone is REQUIRED in SignUpForm and ProfileForm (Iranian mobile `09` + 9 digits, normalised); the model field stays `blank=True` (no migration), so admin-created users may lack a phone: SMS is then logged as `skipped`. | SMS needs a number | final |

## 4. docs/DOMAIN.md — edits
a) In section **catalog → Item**, append to the Item field list: `latitude` (Decimal 9,6, null), `longitude` (Decimal 9,6, null), `address_text` (CharField 255, blank) = pickup point. Add: CheckConstraint "latitude and longitude are both null or both set"; validators latitude −90..90, longitude −180..180.
b) In section **rentals → Rental**, append to the Rental field list: `delivery_address` (TextField, blank; the form requires it when delivery_method = courier), `delivery_latitude`, `delivery_longitude` (Decimal 9,6, null, both-or-none constraint), `reminder_sent_at` (DateTimeField, null).
c) Replace the text of section **core** (currently "No models required...") with:
**NotificationLog**: user (FK User, null, SET_NULL), channel (email / sms), event (signup_confirmation / item_registered / rental_ending_soon), recipient (CharField), subject (blank), body (TextField), status (sent / failed / skipped), error (blank), item (FK null), rental (FK null), created_at. Index (event, created_at).
Core also holds: notifications.py, sms.py, middleware (request logging), cookie helpers, error views.
d) In the ER mermaid block add: `  User ||--o{ NotificationLog : receives`

## 5. tasks/phase-2.md — INSERT these blocks (unchecked)
Insert **P2-01A** and **P2-02A** right after the block of `P2-01 Base layout`/`P2-02 accounts` as stated below; **P2-03A** after `P2-03`; **P2-04A, P2-04B** after `P2-04`; **P2-05A** after `P2-05`.

Insert directly AFTER block `P2-01 Base layout`:
- [ ] **P2-01A Notification foundation (email + SMS)**
  - Files: `core/models.py` (NotificationLog per DOMAIN), `core/sms.py`, `core/notifications.py`, `core/admin.py`, `templates/notifications/<event>_subject.txt` and `<event>_body.txt` for the 3 events (Persian text, short), `config/settings.py` (EMAIL_BACKEND from env default console, DEFAULT_FROM_EMAIL, `SMS_BACKEND` default `console`), migration.
  - Goal: `notify(user, event, context=None, *, item=None, rental=None)` renders the event templates, sends email (Django `send_mail`) and SMS (backend from `get_sms_backend()`), writes one NotificationLog row per channel (`sent` / `failed` / `skipped` when user has no email or phone). Exceptions are caught, stored in `error`, never re-raised. Backends: `ConsoleBackend` (prints), `LocmemBackend` (list `sms.outbox`).
  - Acceptance: in `manage.py shell`, `notify(user, "signup_confirmation")` prints the email and SMS in the console and creates 2 log rows; a user without phone gets an sms row with status `skipped`; a backend that raises produces a `failed` row and no exception; rows visible in admin.
  - Commits: `feat(core): add NotificationLog model` · `feat(core): add SMS backends and notify service`
  - Done notes:

Insert directly AFTER block `P2-02 accounts: auth + profile`:
- [ ] **P2-02A Signup confirmation by email and SMS**
  - Files: `accounts/forms.py` (phone required + validator `^09\d{9}$` + normalisation in SignUpForm and ProfileForm), `accounts/views.py` (call `notify(user, "signup_confirmation")` after successful signup), templates (phone field).
  - Acceptance: signup without/invalid phone shows a Persian error; valid signup → logged in, console shows confirmation email AND SMS, 2 NotificationLog rows; a notification failure (simulate by raising in backend) does not stop signup.
  - Commit: `feat(accounts): require phone and send signup confirmation`
  - Done notes:

Insert directly AFTER block `P2-03 catalog: browse + detail`:
- [ ] **P2-03A Geo fields migration (instructor change)**
  - Files: `catalog/models.py`, `rentals/models.py`, both `admin.py`, NEW migrations only (never edit old migrations).
  - Goal: add the fields from DOMAIN.md: Item latitude/longitude/address_text; Rental delivery_address/delivery_latitude/delivery_longitude/reminder_sent_at; constraints and validators.
  - Acceptance: `makemigrations` creates one new migration per app; `migrate` OK on the existing database with existing rows; shell: lat without lng raises IntegrityError; latitude 120 fails `full_clean()`.
  - Commit: `feat(catalog): add pickup location fields` · `feat(rentals): add delivery location and reminder fields`
  - Done notes:

Insert directly AFTER block `P2-04 catalog: owner management`:
- [ ] **P2-04A Map: choose and show item location**
  - Files: `templates/partials/map_picker.html`, `templates/partials/map_view.html`, `catalog/forms.py` (ItemForm gets latitude, longitude as hidden fields + address_text), item create/edit templates, item detail template.
  - Goal: Leaflet + OSM (CDN). Picker: click or drag a marker, writes the two hidden inputs, default centre = Tehran. Viewer: read-only map with one marker + the address text. ItemForm `clean()`: both coordinates or none, ranges valid.
  - Acceptance: owner sets a point and it persists; item detail shows the map; item without coordinates shows only the address text and no map; invalid coordinates (tampered POST) are rejected by the form.
  - Commits: `feat(core): add Leaflet map picker and viewer partials` · `feat(catalog): add pickup location to item form and detail`
  - Done notes:

- [ ] **P2-04B Item registration confirmation by email and SMS**
  - Files: `catalog/views.py` (item_create).
  - Goal: after a NEW item is saved call `notify(owner, "item_registered", {"title": item.title}, item=item)`; editing an item does not notify.
  - Acceptance: creating an item prints email + SMS with the title and creates 2 NotificationLog rows linked to the item; edit sends nothing.
  - Commit: `feat(catalog): notify owner when an item is registered`
  - Done notes:

Insert directly AFTER block `P2-05 rentals: request, price, payment, receipt`:
- [ ] **P2-05A Map for the handover location**
  - Files: `rentals/forms.py` (RentalRequestForm: if delivery_method = courier then delivery_address is required; optional pin via hidden delivery_latitude/longitude), rental request template (map_picker, shown only for courier), receipt and rental_detail templates (map_view).
  - Goal: for `pickup` rentals show the ITEM's pickup point; for `courier` rentals show the renter's delivery point; same partials as P2-04A.
  - Acceptance: courier without address is rejected; receipt shows the right map for each method; no map when no coordinates exist.
  - Commit: `feat(rentals): show handover location on map`
  - Done notes:

### In the existing block `P2-09 Test data entry` — APPEND to its "Goal" text:
Also: every user gets a fake phone `0912xxxxxxx`; at least 10 items get coordinates (Tehran, Tabriz, Isfahan neighbourhoods) and address_text; one `handed_over` rental ends in about 2 hours (for the reminder demo) and another ends in 3 days; one courier rental has a delivery point.

### In the existing block `Phase 2 deliverables checklist` — APPEND lines:
- [ ] signup + item registration send email AND SMS (console) and are visible in NotificationLog
- [ ] maps work on item form, item detail, rental request/receipt

## 6. tasks/phase-3.md — edits
a) In block `P3-01 Managers and QuerySets`, in the RentalQuerySet method list add `ending_soon(hours)` (handed_over rentals whose end_at is within now..now+hours and reminder_sent_at is null).
b) Insert directly AFTER block `P3-01 Managers and QuerySets`:
- [ ] **P3-01A Rental-ending reminder (email + SMS)**
  - Files: `rentals/management/commands/send_rental_reminders.py`, `config/settings.py` (`RENTAL_REMINDER_HOURS`, default 3), `templates/notifications/rental_ending_soon_{subject,body}.txt`, README (how to schedule).
  - Goal: command options `--hours` (default from settings), `--loop`, `--interval` (seconds, default 60). For each `Rental.objects.ending_soon(hours)` call `notify(rental.renter, "rental_ending_soon", {title, end_at in Asia/Tehran}, rental=rental)` and set `reminder_sent_at = now()` when at least one channel was `sent`. Print how many reminders were sent.
  - Acceptance: with seed data the 2-hour rental gets exactly one email and one SMS; running the command again sends 0; the 3-day rental and non-handed_over rentals are untouched; README documents cron and Windows Task Scheduler lines.
  - Commits: `feat(rentals): add ending_soon queryset method` (only if not already in P3-01) · `feat(rentals): add send_rental_reminders command`
  - Done notes:
c) In block `P3-04 Logging configuration + middleware` add one sentence to Goal: the notifications code logs every attempt to `amanatyab.core` (event, channel, user id, status); phone numbers are masked (last 3 digits), emails show only the domain; message bodies are never logged.
d) In block `P3-06 Phase 3 wrap-up` add to Files: `docs/REPORT.md` §6 also describes notifications (events, channels, NotificationLog, reminder command) and the map.
e) In `Phase 3 deliverables checklist` append: - [ ] `send_rental_reminders` works and is idempotent

## 7. tasks/phase-4.md — edits
a) In block `P4-01 Email verification` append to Goal: the signup confirmation email from P2-02A gets the verification link added (ONE email, not two); the SMS stays a plain confirmation.
b) In block `P4-02 Tests` append to "Must cover": notifications (locmem mail outbox + `sms.outbox`: sent, skipped without phone, failed backend does not break the request), phone validation, the reminder command (window, status filter, idempotency), geo validation (both-or-none, ranges, courier requires address).
c) In block `P4-04 Complete the report` append: REPORT gets a short "نوتیفیکیشن‌ها و نقشه" part (events, channels, backends, Leaflet/OSM).
d) Insert directly AFTER block `P4-06 Gap-closing pass over phases 1–3`:
- [ ] **P4-06A (optional) Real SMS gateway adapter**
  - Do ONLY if the human has a Kavenegar account/API key. Files: `core/sms.py` (KavenegarBackend using `urllib.request`, no new package), `.env.example` (`SMS_BACKEND`, `KAVENEGAR_API_KEY`, `KAVENEGAR_SENDER`).
  - Acceptance: with `SMS_BACKEND=kavenegar` a signup sends a real SMS; with the default `console` nothing changes; the key never appears in logs or git. Check the request format against the provider's current docs before coding.
  - Commit: `feat(core): add optional Kavenegar SMS backend`
  - Done notes:
e) In `Phase 4 deliverables checklist` append: - [ ] notifications tested; reminder command tested

## 8. docs/STATE.md
Append to "notes for next session": `UPDATE-01 applied: new tasks P2-01A, P2-02A, P2-03A, P2-04A, P2-04B, P2-05A, P3-01A, P4-06A (optional).`
Then set `current_task` ONLY if one of the new tasks sits before the current one and is unticked: set it to the earliest such new task and write in notes that these are catch-up tasks that must be done in file order. Otherwise leave `current_task` unchanged.
