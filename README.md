# RollPig Public Source Mirror

Read-only disaster-recovery mirror tooling for the AstrBot RollPig public resource source.

## Current status: fail closed

Public mirroring is **temporarily disabled** while the provenance and redistribution-rights audit remains open. The stale pre-audit `public/v1` snapshot has been removed from the current repository tree. Git history is intentionally preserved as audit evidence, but it must not be treated as an active publication source.

Accordingly:

- `public/v1/manifest.json` is intentionally absent;
- the Vercel deployment connected to this repository must not serve a RollPig v1 snapshot;
- the scheduled primary-source mirroring job is disabled;
- clients must fall back to their last-known-good local cache or bundled resources when the authoritative primary source is unavailable.

## Restoration requirements

A disaster-recovery mirror may only be restored through a separately reviewed publication change after all of the following are true:

1. the candidate is the same audited **provenance-safe base-only** publication intended for the authoritative public source;
2. `NOTICE.md`, `PROVENANCE.json` and the applicable `LICENSES/` material travel with the published snapshot;
3. unaudited extension material is excluded, including authored EX/EX image payloads, `pig_ex_variants.json`, `roast_copy.json` and historical compatibility-floor payloads unless their redistribution rights are independently established;
4. the mirror validator checks provenance/publication-profile requirements in addition to Resource Protocol integrity, size and SHA-256 checks;
5. the RollPig client independently rejects a mirror that does not satisfy the provenance-safe mirror contract.

Restoring `public/v1` therefore requires changing the fail-closed GitHub Actions guard in the same reviewed change. A normal sync failure must never leave an older publication silently available as a fallback.

## Authoritative source

The authoritative resource source remains:

`https://curryudon.top/astrbot-rollpig/v1/manifest.json`

This repository is non-authoritative. It must not be used to expand, re-license or independently republish third-party resources.

## Security and rights boundary

Review databases, admin tokens, pending submissions, production configuration and other private service state must never be mirrored here. Likewise, source-code licensing must not be assumed to grant redistribution rights for artwork, prose, catalog data or other non-code assets.
