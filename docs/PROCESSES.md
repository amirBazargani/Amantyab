# PROCESSES — website process diagrams (draft; finalised in P1-03)
Persian labels are fine in the final version. Render with any mermaid viewer (GitHub renders them).

## 1. Whole website
```mermaid
flowchart TD
  A[Visitor] --> B{Has account?}
  B -- no --> C[Sign up + email verification]
  B -- yes --> D[Log in]
  C --> D
  D --> E[Home: search items]
  D --> F[My items: create / edit / pause]
  E --> G[Item detail + reviews + chat]
  G --> H[Rental request: dates + delivery]
  H --> I[Simulated payment: rent + deposit]
  I --> J[Receipt + tracking code]
  J --> K[Owner hands over item]
  K --> L[Renter returns item]
  L --> M[Owner confirms return -> completed]
  M --> N[Two-way reviews]
  K --> O[Dispute]
  L --> O
  O --> P[Admin resolves + deposit decision]
```

## 2. Rental state machine
```mermaid
stateDiagram-v2
  [*] --> pending_payment
  pending_payment --> confirmed: payment success
  pending_payment --> cancelled: renter cancels / timeout
  confirmed --> cancelled: either side cancels
  confirmed --> handed_over: owner confirms handover
  handed_over --> returned: renter returns
  returned --> completed: owner confirms OK
  handed_over --> disputed
  returned --> disputed
  disputed --> completed: admin resolves
  completed --> [*]
  cancelled --> [*]
```

## 3. Per-app process description (to be written in Persian in P1-03 → REPORT.md §2)
- accounts: sign up, email verification (P4), login/logout, profile edit, public profile with rating.
- catalog: owner CRUD items + images, pause/activate, public list/search/filter, detail.
- rentals: request, cost calculation, overlap check, simulated payment, receipt, lifecycle actions, cancellation, dispute open/resolve.
- reviews: after completed rental both sides rate 1–5 + comment; averages on profiles and items.
- chat: renter asks owner questions from the item page (conversation per item+renter).
- core: base layout, logging middleware, cookies/session helpers, error pages.
