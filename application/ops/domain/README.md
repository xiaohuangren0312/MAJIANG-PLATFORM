# hqlmajiang.com production domain

2026-09-19: user registered domain; ICP approval pending. Both apex and www currently fail DNS resolution from host. Existing production IP access remains unchanged.

DNS: A @ and A www -> 47.97.85.253. Open TCP 80 and 443 in cloud security group. Do not add AAAA unless IPv6 is configured.

Canonical URL: https://hqlmajiang.com; www redirects to apex. Management stays /manage/.

The .pending nginx file is a preparation artifact, NOT an active site. Nginx and certificate issuance are still required. Before activation: confirm ICP approval and DNS, install nginx, provision a certificate covering both hostnames using ACME with all state/cache/logs under /data/majiang/prod, configure renewal plus validated nginx reload, create temp directories owned by nginx worker, and run nginx -t. Confirm certificate paths against the installed client; do not copy private keys into Git.

At HTTPS cutover: bind production Gunicorn to loopback, set HQL_BEHIND_HTTPS_PROXY=1 (application settings supports this flag), close public 8771, enable pending nginx site. Verify HTTP/www redirects, TLS chain, login/logout, CSRF-protected form, image uploads and data exports. Never enable trusted proxy headers with publicly reachable Gunicorn. Add approved ICP footer information then.

Rollback: disable domain proxy and restore backed-up production systemd drop-ins. Preserve production data and existing release. Domain setup never copies dev events or credentials.

## 2026-09-19 user authorized immediate domain cutover

Nginx and certbot installed. Active HTTP-only site: /data/majiang/prod/config/domain/http.conf, linked from /etc/nginx/sites-enabled/hqlmajiang.conf. Apex and www proxy to 127.0.0.1:8771; other hosts return 444. Nginx runs workers as majiang-prod; log/body/proxy temp files are in production data disk directories; systemd requires /data/majiang/prod. Existing public 8771 remains until HTTPS validation succeeds; dev 8770 unchanged.

Production whitelist drop-in: /etc/systemd/system/hql-prod.service.d/zz-domain.conf. TLS proxy flag remains OFF. Local Host-header /health/ request through nginx returns prod OK. Public DNS A and NS both NXDOMAIN from 223.5.5.5 on 2026-09-19 10:13 CST, so domain accessibility and TLS issuance are blocked on DNS activation, not claimed complete. User says A records and ports are configured.

Default certbot.timer disabled to avoid default system-disk state. No certificate issued yet. Use --config-dir /data/majiang/prod/config/acme --work-dir /data/majiang/prod/tmp/acme --logs-dir /data/majiang/prod/logs/acme for issuance/renewal; install a dedicated renewal timer after success. Pending TLS config must use the actual resulting certificate paths. Application proxy setting is committed in dev, must be released before HTTPS activation.
