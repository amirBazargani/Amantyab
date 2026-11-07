# DECISIONS (append new ones; never silently change old ones)
| ID | Decision | Why | Status |
|----|----------|-----|--------|
| D-01 | One admin (`is_staff`) + normal users who can be owner AND renter | user's requirement | final |
| D-02 | Pages are rendered by Django templates + Django Forms (matches the PDF's Phase 2 literally). React + Tailwind are used as "islands" mounted inside templates (Vite build), added in Phase 4 task P4-04. Tailwind via CDN until then. Same-origin session auth, no DRF, no CORS. | satisfies the rubric AND the Django+React stack with the least moving parts for one developer | **ask instructor: is a pure React SPA allowed instead?** If yes: see "D-02 alt" below |
| D-03 | PostgreSQL only; dev DB via docker-compose; DB dump in `db_backup/` per phase | PDF requirement | final |
| D-04 | UI Persian, RTL, font Vazirmatn (CDN). Code/commits English | course language | final |
| D-05 | Payments simulated (Payment rows, receipt_no, tracking_code) | PDF: no bank gateway needed | final |
| D-06 | Instructor change request 1 puts these in scope: email AND SMS for signup confirmation, item-registration confirmation and rental-ending reminder; map showing pickup/delivery location. Still excluded: SMS account verification, Permission extras, Pagination, other bonus items. React islands (P4-05) remain a stack requirement. | instructor requirement | final |
| D-07 | Auth: Django session + cookie (needed by Phase 3). Login by username; email required | simple | final |
| D-08 | Overlap rule: two non-cancelled rentals of one item may not intersect in time | prevents double booking | final |
| D-09 | SMS goes through `core/sms.py` with swappable backends: `console` (default; prints + logs), `locmem` (tests; `sms.outbox`), optional real `kavenegar` (P4-04A, stdlib urllib, needs API key). Every send attempt (email or SMS) is stored in `core.NotificationLog`. A failed send is logged and never breaks the user's request. | no real gateway needed for the demo; real one is a config switch | final |
| D-10 | Map = Leaflet 1.9 + OpenStreetMap tiles from CDN, no API key. Vanilla JS in template partials `partials/map_picker.html` and `partials/map_view.html`. Owner picks the item's pickup point by clicking the map; renter may pin a courier delivery point. Needs internet; address text is the fallback. | simplest, explainable | final |
| D-11 | Rental-ending reminder = management command `send_rental_reminders` (no Celery). Window setting `RENTAL_REMINDER_HOURS` (default 3). Idempotent via `Rental.reminder_sent_at`. Scheduled by cron / Windows Task Scheduler, or run with `--loop`. | one developer, no extra infra | final |
| D-12 | Phone is REQUIRED in SignUpForm and ProfileForm (Iranian mobile `09` + 9 digits, normalised); the model field stays `blank=True` (no migration), so admin-created users may lack a phone: SMS is then logged as `skipped`. | SMS needs a number | final |

### D-02 alt (only if the instructor allows React SPA)
Phase 2 becomes: JSON views/serializers (plain Django `JsonResponse` or DRF) + React pages; Django Forms replaced by server-side validation functions. Phase 1 is identical in both cases, so Phase 1 does not depend on this answer.
