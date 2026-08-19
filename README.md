# RollPig Public Source Mirror

Read-only disaster-recovery mirror for the AstrBot RollPig public resource source.

## Source priority

RollPig clients should use sources in this order:

1. **Primary** — `https://curryudon.top/astrbot-rollpig/v1/manifest.json`
2. **Vercel mirror** — deployment of this repository
3. **GitHub raw fallback** — this repository's `public/v1` tree
4. Last-known-good local cache / bundled bootstrap resources

The primary source remains authoritative and is expected to update first.

## How this mirror updates

`.github/workflows/sync-primary.yml` checks the primary manifest on a schedule and on manual dispatch. When `resource_version` changes, `scripts/sync_primary.py`:

- downloads the complete Resource Protocol v1 snapshot into a temporary directory;
- validates the client/schema contract, safe relative paths, declared sizes and SHA-256 hashes;
- refuses oversized packages or unsafe paths;
- replaces `public/v1` only after the whole snapshot validates;
- writes `public/v1/mirror.json` with non-authoritative mirror metadata.

The workflow commits the validated snapshot back to this repository. A Vercel project connected to this repository can therefore deploy automatically on every mirror update. If the primary becomes unavailable, this repository and the last successful Vercel deployment keep serving the last validated snapshot.

## Security boundary

This repository contains **published public resources only**. Review databases, admin tokens, uploaded pending submissions, production configuration and other private service state must never be mirrored here.
