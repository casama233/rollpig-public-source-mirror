# RollPig Public Source Mirror

Read-only disaster-recovery mirror for the AstrBot RollPig public resource source.

## Source priority

RollPig clients should use sources in this order:

1. **Primary** — `https://curryudon.top/astrbot-rollpig/v1/manifest.json`
2. **Vercel mirror** — deployment of this repository
3. **GitHub raw fallback** — this repository's `public/v1` tree
4. Last-known-good local cache / bundled bootstrap resources

The primary source remains authoritative and is expected to update first.

## Vercel deployment

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fcasama233%2Frollpig-public-source-mirror&repository-name=rollpig-public-source-mirror&project-name=rollpig-public-source-mirror)

Import this public repository as a Vercel project. Keep the repository root as the project root and let `vercel.json` provide the build command and `public` output directory. Git Integration then redeploys the validated static snapshot on every mirror commit; no runtime proxy to the primary source is required.

After the first production deployment, use the actual stable production domain's `/v1/manifest.json` URL in the RollPig plugin configuration. Do not assume the generated `*.vercel.app` hostname until Vercel has created the project and confirmed its production alias.

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
