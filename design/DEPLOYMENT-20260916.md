# 2026-09-16 生产首次部署

用户授权完成本批提交、Git 推送、dev/prod 更新。验收记录见 ACCEPTANCE-20260916.md。

开发保留 `/data/majiang/dev/app` 的并行开发改动；这些未提交的选秀模块不包含在生产发布。生产从 Git 已提交版本导出到 `/data/majiang/prod/releases/<commit>`，校验后切换 `current`。

生产部署：root 执行 `python3 application/ops/deploy_production.py --revision <commit>`。脚本核验数据盘 UUID，使用独立 majiang-prod 和 pg-hql-prod 账户、虚拟环境、签名密钥、PostgreSQL 实例、数据库、上传及日志目录，迁移前生成本地备份。不得将开发库或登录资料直接复制到生产。

生产应用：hql-prod，127.0.0.1:8771；数据库：hql-postgres-prod，Unix socket `/data/majiang/prod/data/pg-run`、5434、hql_prod、majiang-prod，peer 认证，不监听 TCP。服务自启动并依赖 /data 挂载。新生产管理员由 bootstrap_prod 创建，密码随机生成并仅存于生产 config/admin-login.txt；重复执行不重置密码。

本机 SSH 隧道：开发 8780→8770，生产 8781→8771；页面 `/`，后台 `/manage/`。本地启动器 G:/hql/打开开发环境.cmd 和 G:/hql/打开生产环境.cmd。服务部署于远端，127.0.0.1 地址需这台电脑的隧道保持在线。尚未配置公网域名、反向代理或 HTTPS，不将此部署描述为公网发布。

生产初始为空库；历史数据导入须用户明确选择后执行。首次迁移前备份虽为空库仍保留；未来回滚需检查迁移兼容性，不能只切换软链接。备份与应用位于同一数据盘，不是异地灾备。

## 2026-09-17 公网访问

用户明确授权先通过 HTTP 开放生产网站及管理端，之后补 HTTPS。hql-prod.service.d/public.conf 覆盖监听为 0.0.0.0:8771，HQL_ALLOWED_HOSTS 加入 47.97.85.253；开发仍为 loopback。安全组入方向放行 TCP 8771。展示 http://47.97.85.253:8771/，管理 http://47.97.85.253:8771/manage/。systemd drop-in 独立于基础部署脚本，后续发布保留公网配置。数据库仍不监听 TCP。
