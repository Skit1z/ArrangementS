# 部署与操作手册

党政办公室会议场地排班系统。容器化部署（Docker Compose），Caddy 反向代理（自动 HTTPS），Postgres 持久化，APScheduler 单进程周期任务。

## 架构

```
                    ┌──────────┐
       :80/:443 ───▶│  caddy   │── /api/*,/health ──┐
                    │ (TLS)    │                     ▼
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
                      ┌───────────┐    ┌──────────┐│
                      │  postgres │    │  redis   ││（仅登录限速，内存回退）
                      └───────────┘    └──────────┘│
```

| 服务 | 作用 |
|---|---|
| `postgres` | 业务数据（人员、排班、统计等） |
| `redis` | 登录失败计数；不可用时自动回退到 api 进程内字典 |
| `api` | FastAPI REST；启动时自动 `alembic upgrade head` + 幂等种子（admin/场地/倍率） |
| `worker` | 周期任务：班次自动完成（5 分钟）、学期结束旧课表失效（每日 02:00 UTC） |
| `caddy` | 反向代理 + 前端 SPA 静态托管 + 自动 HTTPS |

---

## 一、首次部署

### 1. 环境准备

- Docker + Docker Compose v2
- 一台可被内网/公网访问的服务器
- （可选）域名 + A 记录指向服务器，用于自动 HTTPS

### 2. 生成密钥

```bash
# JWT / CSRF / APP 通用密钥（各自独立生成）
python -c "import secrets; print(secrets.token_urlsafe(48))"

# 字段加密密钥（身份证号 / 银行卡号 用 AES-256-GCM；离线妥善保管，丢失则密文不可恢复）
cd apps/api && .venv/bin/python -c "from app.core.crypto import generate_key_b64; print(generate_key_b64())"
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，至少改：
#   JWT_SECRET / CSRF_SECRET / APP_SECRET       ← 上一步生成的值
#   FIELD_ENCRYPTION_KEY                         ← 上一步生成；生产必填
#   POSTGRES_PASSWORD                            ← 改强密码（与 POSTGRES_USER/DB 配套）
#   COOKIE_SECURE=true                           ← 启用 HTTPS 后
#   CORS_ORIGINS=https://your-domain             ← 正式域名
```

完整变量见下方[环境变量参考](#环境变量参考)。

### 4. 构建前端

```bash
cd apps/web
pnpm install
pnpm build         # 产物在 apps/web/dist/
cd ../..
```

`dist/` 会被 compose 以只读卷挂进 caddy 容器（`/srv/web`）。

### 5. 启动

```bash
cd infra
docker compose up -d --build
```

启动顺序：postgres/redis 健康检查通过 → api 跑迁移 + 种子 + uvicorn → worker 启动周期任务 → caddy 代理。首次拉镜像 + 构建 OR-Tools 可能耗时数分钟。

### 6. 验证

```bash
docker compose ps                       # 所有服务应为 healthy / running
curl -fsS http://localhost/health       # {"status":"ok","env":"production"}
```

浏览器访问 `http://<域名或IP>/`，应见登录页。默认管理员：

```
admin / admin1234
```

**首次登录后请立即在「系统配置」或通过 admin 改密接口修改默认密码。**（注：系统未强制改密 DB 字段，依赖此程序性约束。）

### 7. 启用 HTTPS（正式域名）

编辑 `infra/Caddyfile`，把首行 `:80 {` 改为实际域名：

```
schedule.example.edu.cn {
    ...
}
```

caddy 会自动向 Let's Encrypt 申请并续期证书（需服务器 80/443 可达）。同时确认 `.env`：

```
COOKIE_SECURE=true
CORS_ORIGINS=https://schedule.example.edu.cn
```

重启 caddy：`docker compose restart caddy`。

---

## 二、日常运维

### 日志

```bash
docker compose logs -f api       # API + uvicorn
docker compose logs -f worker    # 周期任务（auto-complete / expire-semesters）
docker compose logs --tail=200 caddy
```

uvicorn 与 worker 日志均走 stdout（无文件卷），由 docker 日志驱动管理；如需落盘可配 `json-file` 的 `max-size`/`max-file`。

### 健康检查

- 应用层：`GET /health` → `{"status":"ok",...}`
- 容器层：`api`（curl /health）、`postgres`（pg_isready）、`redis`（redis-cli ping）、`worker`（进程存在）

### 升级

```bash
git pull
cd ../apps/web && pnpm install && pnpm build && cd ../..
cd infra
docker compose up -d --build         # api 启动时自动 alembic upgrade head
```

迁移均为追加式（0001→0007 线性链），向前兼容。若需在升级前手动验证迁移：

```bash
docker compose exec api alembic upgrade head --sql   # 预览 SQL 不执行
```

### 回滚

```bash
# 回退到上一版本镜像
git checkout <prev-commit>
docker compose up -d --build
# 若新迁移已执行且需回退 schema（谨慎）：
docker compose exec api alembic downgrade -1
```

> ⚠️ 回退 schema 通常不可逆且可能丢数据，务必先备份。

---

## 三、备份与恢复

### 备份

`infra/scripts/backup.sh` 备份三项：Postgres 逻辑转储、文件存储（上传的人员 Excel 等）、字段加密密钥。建议用 cron 每日执行：

```bash
# crontab -e
# 每日 03:00 在 api 容器内跑备份
0 3 * * * docker compose -f /opt/ArrangementS/infra/docker-compose.yml exec -T api sh /app/infra/scripts/backup.sh >> /var/log/scheduler-backup.log 2>&1
```

> 注：脚本默认输出到 `infra/backup/`（容器内为 `/app/infra/backup/`）。若希望落到宿主机，请把该目录挂为卷，或设 `BACKUP_DIR`。

备份保留期由 `BACKUP_RETENTION_DAYS`（默认 30）控制，脚本自动清理超期文件。

**关键提醒**：备份包内含 `FIELD_ENCRYPTION_KEY`（恢复身份证/银行卡密文必需）。请将备份**离线妥善保管**（外置盘 / 异地），切勿与代码仓库同存。

### 恢复

```bash
# 1. 停服务，避免恢复期间写入
docker compose stop api worker

# 2. 恢复 DB（覆盖现有数据）+ 可选文件存储
docker compose exec postgres sh -c 'gunzip -c /backup/db.sql.gz | psql "$DATABASE_URL"'
# 或在宿主机：RESTORE_FILES=1 sh infra/scripts/restore.sh infra/backup/backup_YYYYMMDD_HHMMSS.tar.gz

# 3. 确认 .env 的 FIELD_ENCRYPTION_KEY 与备份一致（否则密文字段无法解密）

# 4. 重启并核对
docker compose start api worker
curl -fsS http://localhost/health
```

恢复前务必在测试环境演练一次。

---

## 四、环境变量参考

| 变量 | 用途 | 默认 / 说明 |
|---|---|---|
| **应用** | | |
| `APP_ENV` | 环境 | `development`；生产设 `production`（影响密钥校验严格度） |
| `APP_SECRET` | 应用通用密钥 | `.env.example` 有；当前 app 读取有限，预留 |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `PUBLIC_BASE_URL` | 对外基地址 | `http://localhost:8000` |
| `MAX_UPLOAD_MB` | 上传上限 | `20` |
| **数据库 / 缓存** | | |
| `DATABASE_URL` | Postgres 连接串 | `postgresql+psycopg://scheduler:scheduler@...` |
| `REDIS_URL` | Redis 连接串 | 仅登录限速；不可用自动回退内存 |
| **安全** | | |
| `JWT_SECRET` | JWT HS256 签名 | **生产必改**（≥32 字节） |
| `CSRF_SECRET` | 双提交 CSRF 令牌 | **生产必改**（≥32 字节） |
| `FIELD_ENCRYPTION_KEY` | AES-256-GCM 字段密钥 | base64(32B)；**生产必填**，空值启动即报错 |
| **令牌 / Cookie** | | |
| `ACCESS_TOKEN_TTL_MINUTES` | 访问令牌寿命 | `60` |
| `REFRESH_TOKEN_TTL_DAYS` | 刷新令牌寿命 | `14` |
| `COOKIE_SECURE` | 仅 HTTPS 传输 | `false`；上线改 `true` |
| `COOKIE_DOMAIN` | Cookie 域 | 留空；跨子域时设置 |
| `CORS_ORIGINS` | 允许源（逗号分隔） | `http://localhost:5173`；生产改正式域名 |
| **登录限速** | | |
| `LOGIN_MAX_FAILURES` | 失败次数阈值 | `5` |
| `LOGIN_LOCK_SECONDS` | 锁定时长 | `300` |
| **存储 / 备份** | | |
| `FILE_STORAGE_PATH` | 上传文件目录 | `/var/app/files`（容器内） |
| `BACKUP_RETENTION_DAYS` | 备份保留天数 | `30`；仅 `backup.sh` 读取 |
| **Postgres 容器** | | |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | 容器初始化 | `scheduler` / `scheduler` / `scheduler`；生产改密码 |

---

## 五、密钥轮换

- **`JWT_SECRET` / `CSRF_SECRET`**：改 `.env` 后重启 api 即可。副作用：所有已签发令牌失效，用户需重新登录。可接受。
- **`FIELD_ENCRYPTION_KEY`**：⚠️ **本项目暂无自动轮换迁移代码**。直接换密钥会导致历史身份证/银行卡密文无法解密。若必须轮换，需自行编写一次性脚本：用旧密钥解全部密文 → 换新密钥重加密 → 原子切换。轮换前**必须**有完整备份。
- **`POSTGRES_PASSWORD`**：改密码需同时改 `DATABASE_URL` 与 Postgres 容器内用户密码（`ALTER USER`），否则 api 连不上。

---

## 六、常见问题

| 现象 | 排查 |
|---|---|
| 启动报错 `FIELD_ENCRYPTION_KEY` 为空 | 生产环境（`APP_ENV=production`）此密钥必填；按"生成密钥"步骤生成后填 `.env` |
| 登录写操作 403 `CSRF 校验失败` | 浏览器未收到 `csrf_token` cookie；检查 `COOKIE_DOMAIN`/`COOKIE_SECURE` 是否与访问域名匹配 |
| `docker compose up` 卡在构建 | OR-Tools 首次编译耗时；或检查网络能否拉取 `python:3.12-slim` |
| 排班班次一直显示「待值班」不自动完成 | 检查 `worker` 是否 running（`docker compose ps`）；其日志应每 5 分钟打印 auto-complete |
| 学期结束后旧课表仍参与冲突 | 检查 worker 日志的 expire-semesters 是否在 02:00 UTC 触发；确认 `semesters.is_current` 已被置 False |
| 前端 404 / 空白页 | 确认 `apps/web/dist` 存在且 compose 已加载新卷挂载；`docker compose restart caddy` |
| 统计导出失败 | 导出走浏览器直连 `/api/v1/statistics/.../export`，需已登录 cookie；确认未跨域 |

---

## 七、服务管理速查

```bash
docker compose up -d --build       # 构建并后台启动
docker compose ps                  # 状态
docker compose logs -f api worker  # 跟踪日志
docker compose restart api         # 重启单服务
docker compose down                # 停止并删容器（卷保留）
docker compose down -v             # ⚠️ 连同数据卷一起删（彻底重置）
```
