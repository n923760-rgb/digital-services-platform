# CORE-001 financial and order kernel

This is an internal foundation for the first vertical slice. It does not accept live orders or expose wallet credits through an API. A trusted payment or authorized admin integration must authenticate and audit before calling `credit`.

All amounts use integer halalas (100 halalas = 1 SAR). The balance is derived from append-only ledger entries; the wallet row exists for per-user transaction locking, never as the financial source of truth. PostgreSQL rejects ledger UPDATE and DELETE. `RESERVE` moves available funds to held funds; `CAPTURE` consumes held funds; `RELEASE` returns them. Each order has at most one reservation and one settlement, enforced by unique partial indexes. Credits, reservations and settlements each require an idempotency key scoped to the wallet.

`confirm_order` serializes requests on the wallet row and commits an immutable order price snapshot, reservation and PENDING job in the same transaction. Insufficient funds roll back the order and job. A repeated request key for the same user/service/channel returns the original order. Services are disabled by default and must be explicitly enabled after their processor and quality rules are available.

Next before serving customers: collect and validate inputs; persist job dispatch reliably; implement worker execution and quality review; make order/job transitions explicit; settle only after validated delivery or release after exhausted retries; integrate files, Telegram and admin visibility. Payment top-ups require a signed, idempotent provider webhook. Direct ledger writes must be restricted to the application's database role in production; the immutability trigger protects against normal UPDATE/DELETE, not database administrators.

The migrated PostgreSQL integration suite covers double submits, concurrent balance contention, refund of held funds through release, settlement replay, price snapshots, insufficient funds rollback, reasoned adjustments and database-enforced immutability. Use a dedicated disposable database when running tests; records use unique IDs but tests do not delete financial history.
