# Native Telegram Stars integration

اعتمد المالك نجوم تلغرام والدفع المباشر لكل طلب. هذا التغيير يضيف التسعير بعدد النجوم والفاتورة المرتبطة بالعرض وتأكيد الدفع الدائم والاسترداد الحقيقي، دون تحويل النجوم إلى المحفظة السابقة بالريال.

## Source and authority

Verified base main de647535874b62edce2a7782090cc1fe9208c955, tree def95a012206d3d31818dcc22a4c72a32921048d; no competing open PR. Owner explicitly selected Stars and direct payment per order, with persistent authority to merge qualified engineering work. Root/project/roadmap and financial/Telegram/file/recovery contracts and skills were read; central reference remains 641e4f9e45da109257ba1f38752b94604c2e4531. Capabilities: repository API and external CI; local shell commands NOT RUN. No subagents used.

## Current official evidence

No-credential public-document run [36939338230](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36939338230), job 110626921705 read current Telegram payments-stars and Bot API sections. Captured body hashes and links are in [the contract](../../docs/TELEGRAM-STARS.md). Locked aiogram is 3.31.0; no dependency/lock changes. Temporary reference workflow is removed from the final tree.

## Implementation boundaries

Native XTR is a separate charge/event path with whole-Star service/order snapshots. Migration 0016 preserves SAR data, enforces currency/amount consistency and refuses destructive financial downgrade. OWNER Stars price edits retain Origin, strict types/range, revision and immutable audit; the bot and new admin forms use Stars.

The quote displays configured actual terms, and invoice storage retains their text/digest, exact amount, ordered inputs, quote revision and buyer. Checkout validates these boundaries before issuing approval within bounded database time. Payment approval alone starts no job. Durable polling inbox insertion precedes offset acknowledgement; background handlers keep slow uploads off checkout polling. Typed paid/refund receipts are processed independently of new-checkout flags. Concurrent/replayed paid receipts create one order/job; invalidated/unfulfillable or additional charges are retained for refund.

Application delivery recognition follows a real receipt. Terminal job/delivery failure requests refundStarPayment; no SAR conversion/credit/reserve/release occurs. Retry claims commit before provider I/O; only positive response, authenticated refund update or matching outgoing transaction evidence confirms refund. Refunds can arrive before paid receipts and prevent execution; earlier completed history remains recorded. Customer status and admin counters expose pending/refunded state without private provider identifiers.

## Qualification preparation

Initial implementation source bfeb0c04bd5f4f8fad339a2494db4853172a80a2 failed Python lint (explicit exception boundaries/import/fixture literal corrected) while web passed. Intermediate source 735bdb7f28e00287a6e175caf5a4c39e9abd49d2 passed lint/migration/web/Compose but found test setup issues: old upload mocks lacked new gate settings, and a refund test assumed its charge was inside the first bounded five-row batch. Fixtures were updated without weakening gate/batch behavior.

Intermediate exact source 5844a60bb21cf3c293869c5a52e4ec9aaea82924, Foundation push [36941546257](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36941546257): python 110633962636 PASS, 133 tests and migration 0016; web 110633962480 PASS including actual Chromium integer-Stars editor/fraction rejection and preserved SAR history. Additional OWNER API/Origin/strict-price/revision and polling-DB-failure offset regressions were then added. This intermediate evidence is not final-source proof.

Final PR [#40](https://github.com/n923760-rgb/digital-services-platform/pull/40) body and exact-source Foundation/advisory logs record final qualification after full diff review. This report is a preparation snapshot, not a premature final PASS.

## Unqualified production work

New checkout/order/service gates stay off. Prices, final purchase terms/support contact and actual disposable bot/payment/refund tests need owner configuration/authorized staging. No real Stars charge/refund, deployed token, production migration, paid activation or deployment was exercised.

Remaining: latest-100 history reconciliation does not cover older disputes/chargebacks/off-host restores; pending cases require an operator procedure. Global handler/load qualification and in-flight send/refund races are not exactly-once guarantees. Production S3/IAM/document safety, independent database/object recovery, monitoring and final launch authority remain required. [Canonical roadmap](../MASTER_ROADMAP.md).
