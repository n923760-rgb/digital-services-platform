"""Validate/report public dependency-advisory responses; never masks unavailable scans."""

import json
import os
from pathlib import Path


def main() -> None:
    reports = {}
    failures = []
    for ecosystem, path in (
        ("python", "/tmp/dsp-python-audit.json"),
        ("npm", "/tmp/dsp-npm-audit.json"),
    ):
        report_path = Path(path)
        if not report_path.is_file():
            failures.append(f"{ecosystem}: report unavailable")
            continue
        report = json.loads(report_path.read_text())
        reports[ecosystem] = report
        print("ADVISORY_REPORT=" + json.dumps({"ecosystem": ecosystem, "report": report}), flush=True)
    if "python" in reports:
        dependencies = reports["python"].get("dependencies")
        if not isinstance(dependencies, list) or not dependencies:
            failures.append("python: invalid/empty dependency report")
        else:
            if any(not isinstance(item, dict) or not item.get("name") for item in dependencies):
                failures.append("python: malformed dependency entries")
            skipped = [item for item in dependencies if "skip_reason" in item]
            vulnerable = [item for item in dependencies if item.get("vulns")]
            print(f"Python audited {len(dependencies)} dependencies; skipped {len(skipped)}; "
                  f"vulnerable packages {len(vulnerable)}")
            if skipped or vulnerable:
                failures.append("python: skipped dependencies or known advisories")
    if "npm" in reports:
        report = reports["npm"]
        metadata = report.get("metadata", {})
        vulnerabilities = metadata.get("vulnerabilities", {})
        if report.get("error") or "total" not in vulnerabilities:
            failures.append("npm: registry error or invalid report")
        elif vulnerabilities["total"]:
            failures.append("npm: known production advisories")
        print("npm production vulnerability summary: " + json.dumps(vulnerabilities))
    print("ADVISORY_SOURCE=" + os.environ.get("GITHUB_SHA", "unknown"), flush=True)
    if failures:
        raise SystemExit("; ".join(failures))
    print("Advisory checks PASS: no reported known vulnerabilities in scanned app locks; "
          "not proof of absence, image/OS safety or production readiness", flush=True)


if __name__ == "__main__":
    main()
