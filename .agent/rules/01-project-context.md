# Project context
- Product: users list idle items; other users rent them by the hour/day. Platform takes 15% commission from the owner side.
- Roles: ONE admin (`is_staff`) + normal users. Every normal user can be owner AND renter (never both on the same rental).
- Core flow: search → item detail → rental request (dates, delivery method) → simulated online payment (rent + deposit) → receipt + tracking code → handover → return → completed → two-way reviews. Disputes are resolved by admin.
- No real payment gateway (simulated Payment records only).
- Source of truth for models: docs/DOMAIN.md. For decisions: docs/DECISIONS.md. For process flows: docs/PROCESSES.md.
- Phase scope is defined by the course PDF:
  P1 apps+process design+models | P2 views/urls/templates/forms/test data | P3 managers+session+cookie+logging | P4 email verification+tests+template optimisation+report.
  Do NOT implement items from a later phase early.
- Django apps: accounts, catalog, rentals, reviews, chat, core.
- Every deliverable of a phase also needs a PostgreSQL dump in `db_backup/` (pg_dump, plain SQL) committed to GitHub.
