# PHASE 3 — managers, session & cookie, logging

- [x] **P3-01 Managers and QuerySets**
  - Files: `catalog/models.py` (ItemQuerySet: `active()`, `in_city()`, `in_category()`, `search(q)`, `price_up_to()`, `available_between(start,end)`; `Item.objects = ItemQuerySet.as_manager()`), `rentals/models.py` (RentalQuerySet: `blocking()`, `overlapping(item,start,end)`, `for_renter()`, `for_owner()`, `with_status()`, `ending_soon(hours)` (handed_over rentals whose end_at is within now..now+hours and reminder_sent_at is null)), `reviews/models.py` (ReviewQuerySet: `for_user()`, `average_rating()`), `accounts/models.py` (UserManager if needed for create_user with email).
  - Goal: move ad-hoc ORM from views/services into these. Views get shorter. Document each in REPORT §4 with "why".
  - Acceptance: no query-building logic left in templates; `item_list` uses chained queryset methods; behaviour identical to Phase 2 (re-run QA-P2).
  - Commits: `refactor(catalog): add Item queryset methods` · `refactor(rentals): add Rental queryset methods` · `refactor(reviews): add Review queryset methods` · `docs: describe managers in report`
  - Done notes: Implemented custom ItemQuerySet, RentalQuerySet, and ReviewQuerySet with full method suites and attached via as_manager(); refactored item_list to chained query methods; refactored rentals/reviews views and services; added 15 unit tests (total 133 tests passing); documented §4 in docs/REPORT.md; updated docs/DEFENSE.md and docs/COMMIT-LOG.md.

- [x] **P3-01A Rental-ending reminder (email + SMS)**
  - Files: `rentals/management/commands/send_rental_reminders.py`, `config/settings.py` (`RENTAL_REMINDER_HOURS`, default 3), `templates/notifications/rental_ending_soon_{subject,body}.txt`, README (how to schedule).
  - Goal: command options `--hours` (default from settings), `--loop`, `--interval` (seconds, default 60). For each `Rental.objects.ending_soon(hours)` call `notify(rental.renter, "rental_ending_soon", {title, end_at in Asia/Tehran}, rental=rental)` and set `reminder_sent_at = now()` when at least one channel was `sent`. Print how many reminders were sent.
  - Acceptance: with seed data the 2-hour rental gets exactly one email and one SMS; running the command again sends 0; the 3-day rental and non-handed_over rentals are untouched; README documents cron and Windows Task Scheduler lines.
  - Commits: `feat(rentals): add ending_soon queryset method` (only if not already in P3-01) · `feat(rentals): add send_rental_reminders command`
  - Done notes: Implemented send_rental_reminders management command supporting --hours, --loop, and --interval; configured RENTAL_REMINDER_HOURS in settings.py; formatted end_at in Asia/Tehran for rental_ending_soon notification template; added cron and Windows Task Scheduler docs in README.md; added unit tests verifying idempotency, channel deliveries, and arguments (136 total tests passing).

- [ ] **P3-02 Session management**
  - Files: `config/settings.py`, `accounts/views.py`, `catalog/views.py`.
  - Goal: DB-backed sessions; SESSION_COOKIE_AGE 2 weeks; SESSION_COOKIE_HTTPONLY; "remember me" checkbox on login (`request.session.set_expiry(0)` when unchecked); store last search filters in session and prefill the list page; session cleared on logout; `manage.py clearsessions` noted in README.
  - Acceptance: unchecked remember-me → session ends with browser; search filters persist across pages in same session.
  - Commit: `feat(accounts): add session settings and remember-me` · `feat(catalog): persist search filters in session`

- [ ] **P3-03 Cookie management**
  - Files: `core/cookies.py` (helpers), `catalog/views.py`, `templates/partials/recent_items.html`, home template.
  - Goal: signed cookie `recent_items` (last 6 viewed item ids, max_age 7 days, httponly) and cookie `last_city`; home page shows "recently viewed" and pre-selects city. Helpers use `set_signed_cookie/get_signed_cookie`.
  - Acceptance: cookies visible in browser devtools; tampered cookie is ignored without error.
  - Commit: `feat(core): add cookie helpers` · `feat(catalog): add recently viewed items and last city cookies`

- [ ] **P3-04 Logging configuration + middleware**
  - Files: `config/settings.py` (LOGGING dict: console + RotatingFileHandler `logs/app.log`, separate `logs/security.log`; loggers per app `amanatyab.<app>`), `core/middleware.py` (RequestLogMiddleware: method, path, user id, status, duration ms), `logs/.gitkeep`.
  - Goal: the notifications code logs every attempt to `amanatyab.core` (event, channel, user id, status); phone numbers are masked (last 3 digits), emails show only the domain; message bodies are never logged.
  - Acceptance: every request produces one line in app.log; logs/*.log git-ignored.
  - Commit: `feat(core): add logging config and request log middleware`

- [ ] **P3-05 Add logging to every part of the project**
  - Goal: `logger = logging.getLogger("amanatyab.<app>")` in every views.py/services.py/forms where relevant. Log: login success/failure (security.log), signup, item create/edit/delete/toggle, rental request/payment/every transition/cancel, dispute open/resolve, review create, message send (no body), permission denied (warning), unexpected exceptions (`logger.exception`). Never log passwords, tokens, or message text.
  - Acceptance: grep shows a logger in each app's views; a full demo run produces a readable story in app.log.
  - Commits (one per app): `feat(accounts): add logging` · `feat(catalog): add logging` · `feat(rentals): add logging` · `feat(reviews): add logging` · `feat(chat): add logging`

- [ ] **P3-06 Phase 3 wrap-up**
  - Files: `docs/REPORT.md` §4 and §6 (session, cookie, logging), `docs/DEFENSE.md`. `docs/REPORT.md` §6 also describes notifications (events, channels, NotificationLog, reminder command) and the map. Run `/phase-review`.

### Phase 3 deliverables checklist
- [ ] managers used by views; session + cookies demonstrable in the browser; logs generated for all apps
- [ ] `send_rental_reminders` works and is idempotent
- [ ] `db_backup/phase-3.sql`; tag `phase-3-done`
