# 会议场地排班管理系统

党政办公室会议场地排班系统。服务器部署、浏览器访问。业务基线与验收标准见
[`会议场地排班系统_完整实施方案.md`](会议场地排班系统_完整实施方案.md) 与
[`会议场地排班系统_Fable5验收清单.yaml`](会议场地排班系统_Fable5验收清单.yaml)。

## 仓库结构

```
apps/api/     FastAPI 后端（SQLAlchemy 2 + Alembic + OR-Tools）
apps/web/     React 前端（阶段六接入）
infra/        Docker Compose / Caddy / 备份脚本
docs/         API / 数据库 / 验收文档
```

## 实施进度

- [x] 阶段一 基础工程：认证/角色/审计、配置、数据库迁移体系、工时计算引擎、Docker Compose
- [x] 阶段二 人员与学期：Excel 导入与账号生成、人员管理与自动排班名单、学期/课程时间/教学楼映射、假期与可值班白名单
- [x] 阶段三 课表识别：周次表达解析、节次时间解析、课程规则→不可值班区间（含缓冲）、审核后生效、旧课表逻辑失效；PDF/OCR 抽取层已抽象（待样例接入）
- [x] 阶段四 场地与任务：三场地/黄楼六班次初始化、临时任务(值班时间/同场地重叠/工时预览)、特殊日期与 holiday-cn 同步(待确认)、倍率规则 CRUD 与工时引擎接入、每日人数规则
- [x] 阶段五 排班算法：OR-Tools CP-SAT 求解器（硬约束+月度公平目标+空缺+可复现）、岗位生成(黄楼/任务/假期规则)、可用性矩阵(区间/约束/假期白名单)、生成→求解→落库→发布
- [x] 阶段七 用户业务：不可值班申请(提交/审核/生成区间)、请假(审核后原人员工时清零并空缺)、指定换班与公开替班(审核复检+原子转移+工时归接替人)、未到岗(实际0/平衡保留)、班次自动完成
- [x] 阶段八 统计与上线（后端）：月度工时统计(平衡/实际/分场地动态)、重算与锁定、工时调整、Excel 导出(汇总+明细，敏感字段不进入)
- [x] 阶段六 前端：登录、人员页、拖拽排班主界面、用户移动端各页、admin 场地任务/统计/配置三页
- [x] 阶段九 上线收尾：周期任务运行器(班次自动完成/学期结束旧课表失效)、备份与恢复脚本、部署与操作手册、验收报告

完整部署、运维、备份、密钥轮换、排障步骤见 [`docs/deployment.md`](docs/deployment.md)；验收逐条核验见 [`docs/acceptance/验收报告.md`](docs/acceptance/验收报告.md)。

## 本地开发（后端）

```bash
cd apps/api
uv venv --python 3.12
uv pip install -e ".[dev]"
.venv/bin/python -m pytest        # 运行测试（SQLite 内存库，无需外部依赖）
```

## 本地开发（前端）

```bash
cd apps/web
pnpm install
pnpm dev                          # http://localhost:5173，已代理 /api → :8000
pnpm typecheck && pnpm test && pnpm build
```

## 部署更新命令

```bash
# 前端有变更：本地 build 后 tar 推送到 1Panel 的网站目录
cd apps/web && pnpm build
tar -czvf web_dist.tar.gz -C dist .
scp web_dist.tar.gz aliyun:/opt/1panel/www/sites/arrangements/
ssh aliyun 'cd /opt/1panel/www/sites/arrangements && tar -xzvf web_dist.tar.gz -C . && rm web_dist.tar.gz'
```

## 容器部署

```bash
cp .env.example .env              # 生成并填入密钥（详见 docs/deployment.md）
cd apps/web && pnpm install && pnpm build && cd ../..   # 构建前端
cd infra
docker compose up -d --build      # 自动执行 alembic 迁移 + 初始化默认 admin + 启动 worker
```

默认管理员：`admin` / `admin1234`（首次登录后请立即修改）。

### 周期任务

`worker` 容器跑 `app.tasks.runner`（APScheduler 单进程）：
- 每 5 分钟：班次结束后自动置「已完成」（`auto_complete_after_end`）
- 每日 02:00 UTC：学期结束后旧课表与不可值班区间失效，置学期为非当前

### 备份

```bash
# 每日 cron（在 api 容器内跑）
docker compose exec api sh /app/infra/scripts/backup.sh
# 恢复
RESTORE_FILES=1 sh infra/scripts/restore.sh infra/backup/backup_YYYYMMDD_HHMMSS.tar.gz
```

备份含 Postgres 转储、上传文件、**字段加密密钥**（离线妥善保管，无密钥则身份证/银行卡密文不可恢复）。详见 `docs/deployment.md`「备份与恢复」章节。

### 部署更新命令
```bash
ssh aliyun 'cd /opt/ArrangementS && git pull'
# 若有新迁移,api 重启会自动跑 alembic upgrade
ssh aliyun 'systemctl restart arrangements-api arrangements-worker'
# 前端有变更:本地 build 后 tar 推送
```
