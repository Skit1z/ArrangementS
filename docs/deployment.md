# 部署与操作手册

党政办公室会议场地排班系统。本机 Systemd 部署，1Panel OpenResty 反向代理（自动 HTTPS），Postgres 持久化，APScheduler 单进程周期任务。

## 架构

```
                    ┌──────────┐
       :80/:443 ───▶│ 1Panel   │── /api/*,/health ──┐
                    │OpenResty │                     ▼
                    │ + SPA静态 │              ┌──────────┐
                    └──────────┘              │   api    │ FastAPI / uvicorn
                                              │ (迁移+   │
                                              │  初始化) │
                                              └────┬─────┘
                                                   │
                       ┌──────────┐                │
                       │  worker  │◀───────────────┤  共享 Postgres
                       │ APScheduler│               │
                       │ 周期任务  │               │
                       └──────────┘                │
                      ┌───────────┐
                      │  postgres │
                      └───────────┘
```

| 服务 | 作用 |
|---|---|
| `postgres` | 业务数据（人员、排班、统计等） |
| `arrangements-api` | FastAPI REST（Systemd 服务）；启动时自动 `alembic upgrade head` + 幂等种子 |
| `arrangements-worker` | 周期任务（Systemd 服务）：班次自动完成（5 分钟）、学期结束旧课表失效（每日 02:00 UTC） |
| `1Panel OpenResty` | 反向代理 + 前端 SPA 静态托管 + 自动 HTTPS |

---

## 一、日常运维

### 日志

```bash
journalctl -u arrangements-api -f
journalctl -u arrangements-worker -f
```

### 升级

```bash
ssh aliyun 'cd /opt/ArrangementS && git pull'
# 若有新迁移,api 重启会自动跑 alembic upgrade
ssh aliyun 'systemctl restart arrangements-api arrangements-worker'

# 前端有变更：本地 build 后 tar 推送到 1Panel 的网站目录
cd apps/web && pnpm build
tar -czvf web_dist.tar.gz -C dist .
scp web_dist.tar.gz aliyun:/opt/1panel/www/sites/arrangements/
ssh aliyun 'cd /opt/1panel/www/sites/arrangements && tar -xzvf web_dist.tar.gz -C . && rm web_dist.tar.gz'
```

---

## 二、备份与恢复

### 备份

`infra/scripts/backup.sh` 备份三项：Postgres 逻辑转储、文件存储（上传的人员 Excel 等）、字段加密密钥。建议用 cron 每日执行：

```bash
# 每日 03:00 跑备份
0 3 * * * sh /opt/ArrangementS/infra/scripts/backup.sh >> /var/log/scheduler-backup.log 2>&1
```

> 注：脚本默认输出到 `/opt/ArrangementS/infra/backup/`。

备份保留期由 `BACKUP_RETENTION_DAYS`（默认 30）控制，脚本自动清理超期文件。

**关键提醒**：备份包内含 `FIELD_ENCRYPTION_KEY`（恢复身份证/银行卡密文必需）。请将备份**离线妥善保管**（外置盘 / 异地），切勿与代码仓库同存。

### 恢复

```bash
# 1. 停服务，避免恢复期间写入
systemctl stop arrangements-api arrangements-worker

# 2. 恢复 DB（覆盖现有数据）+ 可选文件存储
RESTORE_FILES=1 sh /opt/ArrangementS/infra/scripts/restore.sh infra/backup/backup_YYYYMMDD_HHMMSS.tar.gz

# 3. 确认 .env 的 FIELD_ENCRYPTION_KEY 与备份一致（否则密文字段无法解密）

# 4. 重启并核对
systemctl start arrangements-api arrangements-worker
curl -fsS http://localhost:8000/health
```

恢复前务必在测试环境演练一次。
