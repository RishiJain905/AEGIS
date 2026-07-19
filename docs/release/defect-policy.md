# Release defect record policy

Every release defect is recorded as a small structured record, either in the release issue
tracker or the retained evidence notes:

`defectId`, `observedAt`, `revision`, `criterion`, `severity` (`B0`–`B3`), `environment`,
`scenario`, `seed`, `reproduction`, `expected`, `actual`, `evidencePaths`, `owner`,
`status` (`open|fixed|accepted|deferred`), `disposition`, `fixedAt`, and
`verificationRunId`.

A defect is `fixed` only after the smallest relevant test and the release stage are re-run.
`accepted`/`deferred` requires an owner, mitigation, expiry, and a linked exception when it
would otherwise block release. Do not replace a reproducible defect with a free-form known-
issue sentence; preserve the exact command, input, and observed output.
