# MAJIANG-PLATFORM

## Server layout

| Purpose | Development | Production |
| --- | --- | --- |
| Service user | majiang-dev | majiang-prod |
| Source / releases | /data/majiang/dev/app | /data/majiang/prod/releases |
| Configuration | /data/majiang/dev/config | /data/majiang/prod/config |
| Persistent data | /data/majiang/dev/data | /data/majiang/prod/data |
| Uploads | /data/majiang/dev/uploads | /data/majiang/prod/uploads |
| Logs | /data/majiang/dev/logs | /data/majiang/prod/logs |
| Cache / temporary files | /data/majiang/dev/cache and tmp | /data/majiang/prod/cache and tmp |
| Local backups | /data/majiang/dev/backups | /data/majiang/prod/backups |

The original /data/MAJIANG-PLATFORM path links to the development checkout.
Environment directories have separate Unix ownership and mode 0750; configuration directories use 0700.
Both service accounts have login disabled. Root administers deployments and repository access.
Run development Git commands as majiang-dev; server GitHub authentication is currently configured for root only.

## Current state

Development application is running under majiang-dev using Django, Gunicorn and PostgreSQL 18.6. Database, dependencies, logs, cache and temporary files are under /data/majiang/dev. Production has not been deployed.
Storage environment templates are outside Git under each environment's config directory; they are not automatically loaded.
Development service: hql-dev, listening on 127.0.0.1:8770; local SSH tunnel uses port 8780. See application/README.md for current capabilities and remaining work.
OS packages and system logs remain on the system disk; application storage must be explicitly configured under /data.
See AGENTS.md for mandatory storage and deployment constraints.

## Authoritative development workspace

Develop directly in /data/majiang/dev/app through SSH as majiang-dev. This remote checkout is the authoritative source. Local G:/hql/application is an earlier staging copy, not an independently maintained checkout. Run edits, migrations, tests and Git status on the remote host. Preserve existing uncommitted changes. Do not deploy to production implicitly.
