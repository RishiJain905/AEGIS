# Third-Party Attribution

The repository CI security workflow generates a CycloneDX dependency SBOM and derives
the attribution input with the `jq` command in
[`.github/workflows/security.yml`](.github/workflows/security.yml). Generate the
release document with:

```powershell
uv run python scripts/generate_third_party_attribution.py `
  --input security-artifacts/license-report.json `
  --output THIRD-PARTY.md
```

No retained CI `license-report.json` is present in this checkout, so the dependency
inventory has not been asserted or copied into this file. The release checklist
requires generating it from the CI artifact before any published distribution. The
report is a visibility control; unknown or restricted licenses require owner/legal
review under [the scan triage policy](docs/security/scan-triage-policy.md).

This repository does not currently contain a `LICENSE` file. No license choice is
invented by this attribution document.
