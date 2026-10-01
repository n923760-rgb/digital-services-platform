# DSP-008 — bounded PDF sandbox liveness
Date 2026-10-01. Baseline c6349e4a554d5fdc97e6b471e0ed964f8c94175f; no open PRs. Owner authorized continued repairs and qualified merging.
Applied root instructions and dsp-file-security; reference previously reviewed at 641e4f9e45da109257ba1f38752b94604c2e4531. API/CI only; local CLI/real Telegram/production NOT RUN.
FACT: scanner touched heartbeat only after process_one returned, while PDF subprocess could legitimately wait 75 seconds; Compose required heartbeat freshness under ten seconds.
Repair: daemon heartbeat guarded by a monotonic progress lease. Scanner gets ten seconds between jobs; parser gets existing timeout plus ten seconds IPC margin. Expired lease stops marker refresh; shutdown removes marker. A stuck loop cannot renew indefinitely through an independent unconditional heartbeat.
Changed pdf_sandbox.py, two tests in test_pdf_sandbox.py, file contract, canonical roadmap and report. Tests prove a separate thread refreshes during simulated blocked scanning and stops at job/idle lease expiry. Parser isolation and limits, wallet/jobs, Docker configuration and launch flags unchanged.
External CI pending at report preparation; associated PR supplies exact-head run/log/merge proof. Full-duration real hostile PDF/load qualification NOT RUN; thread/lease tests plus existing sandbox processing and Compose checks are the scoped evidence.
Worker ARQ remains asynchronous during to_thread processor work and retains existing job timeout/stale recovery. This repair targets the diagnosed sandbox marker. Health failure alone does not cause Docker restart; operational alert/recovery remains required.
Next: DSP-006 trust only the known reverse proxy's forwarded identity; then DSP-007 atomic source/account/pair login limits.
