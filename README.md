# RollPig Public Source Mirror

Read-only disaster-recovery mirror of the existing reviewed RollPig source publication.

The restored snapshot is **2026.09.05.1**, `complete-handwritten-ex`: **164 pigs / 820 EX levels**. It is byte-identical to the source service's published release, including `NOTICE.md`, `PROVENANCE.json`, `LICENSES/` and `EX-AUTHORING.json`. The 68 public-only rights decisions, 96 overlap reviews, historical MIT evidence and completed publication already exist in `casama233/rollpig-public-source-service`; this mirror does not require those decisions to be recreated.

- Primary: https://curryudon.top/astrbot-rollpig/v1/manifest.json
- Vercel mirror: https://rollpig-public-source-mirror.vercel.app/v1/manifest.json
- GitHub fallback: https://raw.githubusercontent.com/casama233/rollpig-public-source-mirror/main/public/v1/manifest.json

Clients require plugin v3.12.3 or later for independently verified mirror failover. They fetch the current approval policy from the fixed GitHub repository, verify the complete snapshot, reject downgrade relative to local cache, and install only the bytes they verified. An unavailable policy prevents a new mirror activation. Private/custom sources remain isolated from this public chain.

## Publication and withdrawal

`publication-approvals.json` is the independent exact-manifest and per-file inventory. Only one current approved snapshot is published. Resource versions are explicit; this frozen mirror does not claim to follow arbitrary new primary releases automatically. New snapshots require their existing source review/publication evidence to be bound to a new exact inventory before refresh.

```bash
python scripts/validate_snapshot.py
python -m unittest discover -s tests -v
python scripts/build_publication.py
```

A manual `python scripts/sync_primary.py` refresh downloads every approved member, never skips validation merely because a version string matches, and cannot approve a new snapshot. Failed downloads preserve the previously approved working tree without pretending the refresh succeeded. Scheduled unreviewed copying remains disabled.

To withdraw a snapshot:

```bash
python scripts/revoke_snapshot.py MANIFEST_SHA256
```

Commit and deploy the resulting policy change and removal of `public/v1` together. Vercel then serves notice-only; GitHub main no longer contains the snapshot. Clients reject removed/revoked approvals on their next successful policy check and move mirror-origin cached assets out of active lookup. A network outage cannot prove a withdrawal, so existing locally verified caches remain available until a current policy can be read. Historical Git commits and old immutable deployment URLs are evidence, not supported automatic fallback targets.

Private reviews, tokens, databases, uploads and quarantined resources are excluded. See [restoration evidence and client contract](RESTORATION.md).
