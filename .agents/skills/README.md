# Project Skills

These are local engineering instructions discoverable under .agents/skills/<name>/SKILL.md.
They do not install external plugins, run tests automatically, grant protected-action permission, or provide unavailable tools.
AGENTS.md owns project policy. Use only the relevant skill after reading its SKILL.md.

| Skill | Use |
| --- | --- |
| [dsp-financial-safety](dsp-financial-safety/SKILL.md) | ledger, orders, provider events, settlement and concurrency |
| [dsp-telegram-workflows](dsp-telegram-workflows/SKILL.md) | callbacks, quote consent, intake, resume/cancel and delivery |
| [dsp-file-security](dsp-file-security/SKILL.md) | uploads, quota/ownership, PDF isolation, retention and recovery |
| [dsp-admin-security](dsp-admin-security/SKILL.md) | role/session/Origin/proxy/throttle boundaries |
| [dsp-arabic-ui](dsp-arabic-ui/SKILL.md) | Arabic RTL, mobile/accessibility, errors and truthful product copy |
| [dsp-release-readiness](dsp-release-readiness/SKILL.md) | exact-source CI, production prerequisites and recovery evidence |

Example request: "Use dsp-financial-safety to diagnose a duplicate settlement on the current verified main; keep diagnosis read-only."
For another repository, start from the central adoption prompt and derive its real architecture. Do not copy this product's wallet/provider facts into unrelated projects.
