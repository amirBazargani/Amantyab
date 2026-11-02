# DOMAIN — models and relations (source of truth)
Money = DecimalField(max_digits=12, decimal_places=0). All models have `created_at` (auto_now_add) unless noted.

## accounts
**User** (extends AbstractUser; `AUTH_USER_MODEL = "accounts.User"` — set BEFORE the first migrate)
- email (unique, required), phone (blank), city, neighborhood, bio (blank), is_email_verified (bool, default False)
- Admin = `is_staff`. No separate role field.

## catalog
**Category**: name, slug (unique), parent (FK self, null)
**Item**: owner (FK User, related_name="items"), category (FK PROTECT), title, description, brand (blank), condition (new / like_new / good / fair), hourly_price (null), daily_price, deposit_amount (default 0), city, neighborhood, allow_pickup (bool), allow_courier (bool), is_active (bool), updated_at
- CheckConstraint daily_price > 0; CheckConstraint allow_pickup OR allow_courier; Index (city, is_active).
**ItemImage**: item (FK, related_name="images"), image (ImageField), is_primary (bool), order (int)

## rentals
**Rental**: item (FK PROTECT), renter (FK User PROTECT, related_name="rentals"), start_at, end_at, delivery_method (pickup / courier), status, rent_amount, deposit_amount, commission_rate (Decimal 0.15), commission_amount, owner_payout, tracking_code (unique, null), updated_at
- CheckConstraint end_at > start_at. Rule in clean(): renter != item.owner; no overlap with another non-cancelled rental of the same item.
- Status: `pending_payment → confirmed → handed_over → returned → completed`; side exits: `cancelled` (from pending_payment/confirmed), `disputed` (from handed_over/returned).
- Pricing (services.py): duration < 24h and hourly_price set → ceil(hours) × hourly_price; else ceil(days) × daily_price. commission = rent × rate; owner_payout = rent − commission.
**Payment** (simulated): rental (FK), kind (rent / deposit / deposit_refund / payout), amount, status (success / failed), receipt_no (unique)
**Dispute**: rental (FK), opened_by (FK User), reason, status (open / resolved), deposit_decision (return_to_renter / give_to_owner / split; blank until resolved), resolution_note, resolved_by (FK User, null), resolved_at (null)

## reviews
**Review**: rental (FK), reviewer (FK User), reviewee (FK User), reviewee_role (owner / renter), rating (1–5, CheckConstraint), comment (blank)
- UniqueConstraint (rental, reviewer): each side reviews once per rental. Allowed only when rental.status == completed.

## chat
**Conversation**: item (FK), renter (FK User); UniqueConstraint (item, renter). Owner = item.owner.
**Message**: conversation (FK), sender (FK User), body, is_read (bool)

## core
No models required. Holds middleware (request logging), context processors, helpers (cookies), error views.

## ER (mermaid)
```mermaid
erDiagram
  User ||--o{ Item : owns
  Category ||--o{ Item : classifies
  Item ||--o{ ItemImage : has
  Item ||--o{ Rental : "is rented in"
  User ||--o{ Rental : rents
  Rental ||--o{ Payment : has
  Rental ||--o{ Dispute : may_have
  Rental ||--o{ Review : "gets (max 2)"
  User ||--o{ Review : writes
  Item ||--o{ Conversation : about
  User ||--o{ Conversation : starts
  Conversation ||--o{ Message : contains
```
