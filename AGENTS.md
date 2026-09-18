# Deployment and storage requirements

- This project uses /data/majiang/dev/app as its development checkout. /data/MAJIANG-PLATFORM is a compatibility symlink.
- Development and production must run as majiang-dev and majiang-prod respectively. Never run application services as root.
- Keep production releases in /data/majiang/prod/releases/<release-id>; use a current symlink only after a verified deployment. Never serve production from the development checkout.
- Keep each environment's databases, uploads, logs, backups, caches, temporary files, dependencies and build outputs on /data and isolated from the other environment.
- Store secrets outside Git in /data/majiang/<env>/config with restrictive permissions. Use separate credentials, databases, ports and networks for development and production.
- storage.env.example contains proposed paths, not an activated configuration. Wire all relevant paths explicitly into the chosen runtime; environment variables alone do not enforce storage placement.
- Before installing Docker or databases, configure their data directories on /data. Docker and containerd storage both require inspection. Bind mount environment-specific application data directories explicitly.
- Application systemd units must use RequiresMountsFor=/data/majiang/<env>, appropriate User/Group, and explicit data/log/cache/temp paths. Fail startup if the data disk is unavailable; never fall back to the root disk.
- Backups on the same disk are local recovery copies, not off-host disaster recovery.
- Do not copy development data or credentials into production automatically.

# Development workflow

- The authoritative development workspace is /data/majiang/dev/app on work-host. Edit and test directly there as majiang-dev via SSH. Do not use a local source copy plus synchronization as the normal development workflow.
- Local files may provide browser access launchers and review artifacts; application source changes belong to the remote checkout.
- Run application tests using /data/majiang/dev/venv/bin/python from application, with PYTHONPYCACHEPREFIX=/data/majiang/dev/cache/pycache and TMPDIR=/data/majiang/dev/tmp.

# Product interaction principles

- This is a personal tournament management backend. Prefer few steps, useful defaults and minimal typing. Operation reasons must be optional; simplify older mandatory-reason flows when updating them.
- Preserve automatic validation of scores, totals, roster membership, qualification, tournament isolation and revision conflicts. Automatically record actor, time and changes.

## Release workflow (user update 2026-09-18)

- Develop and validate every change directly in the authoritative dev checkout. Dev is the integration source.
- Release a verified dev revision to the isolated production release directory when requested or needed for an authorized release. Routine dev edits do not automatically trigger a production deployment.
- Production is a release target, not a second independently developed code line. This supersedes the earlier expectation to publish every edit immediately to both environments.

## Role policy (user update 2026-09-18)

Event managers administer their own unarchived events and may create restricted coach accounts scoped to those events. Coaches gain assigned team-draft actions and their own team’s upcoming match-day lineup scheduling beyond public viewing. Pending lineups must stay private until their scheduled publication time. Viewers cannot perform business writes. Only the total administrator creates/assigns event managers and revises archived events. Preserve score/reference/settlement/revision validation for every role. Archived revisions must retain the last published snapshot until explicitly finalized.

## Delivery UI and temporary historical backfill (2026-09-18)

All seasons use the same delivery management components. Keep S1/S2/S3 source reconciliation, missing-result supplementation and PT inverse tools in the root-only /manage/history-backfill/ workspace. Gate its pages, scripts and APIs with HISTORY_BACKFILL_ENABLED; retiring the workspace must not remove data or affect normal management/public views/exports. Do not reintroduce temporary backfill controls into normal event pages.

- Keep management pages concise as well as public pages: omit workflow essays, implementation details and data-source commentary. Retain field labels, actual records, short input-format hints, validation errors and concrete destructive-action impact previews.
