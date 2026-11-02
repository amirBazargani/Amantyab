# DECISIONS (append new ones; never silently change old ones)
| ID | Decision | Why | Status |
|----|----------|-----|--------|
| D-01 | One admin (`is_staff`) + normal users who can be owner AND renter | user's requirement | final |
| D-02 | Pages are rendered by Django templates + Django Forms (matches the PDF's Phase 2 literally). React + Tailwind are used as "islands" mounted inside templates (Vite build), added in Phase 4 task P4-04. Tailwind via CDN until then. Same-origin session auth, no DRF, no CORS. | satisfies the rubric AND the Django+React stack with the least moving parts for one developer | **ask instructor: is a pure React SPA allowed instead?** If yes: see "D-02 alt" below |
| D-03 | PostgreSQL only; dev DB via docker-compose; DB dump in `db_backup/` per phase | PDF requirement | final |
| D-04 | UI Persian, RTL, font Vazirmatn (CDN). Code/commits English | course language | final |
| D-05 | Payments simulated (Payment rows, receipt_no, tracking_code) | PDF: no bank gateway needed | final |
| D-06 | No bonus items (SMS, maps, Permission extras, Pagination, AJAX) except the React islands needed for the stack | user's requirement | final |
| D-07 | Auth: Django session + cookie (needed by Phase 3). Login by username; email required | simple | final |
| D-08 | Overlap rule: two non-cancelled rentals of one item may not intersect in time | prevents double booking | final |

### D-02 alt (only if the instructor allows React SPA)
Phase 2 becomes: JSON views/serializers (plain Django `JsonResponse` or DRF) + React pages; Django Forms replaced by server-side validation functions. Phase 1 is identical in both cases, so Phase 1 does not depend on this answer.
