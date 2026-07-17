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
- [ ] 阶段二 人员与学期
- [ ] 阶段三 课表识别
- [ ] 阶段四 场地与任务
- [ ] 阶段五 排班算法
- [ ] 阶段六 拖拽界面
- [ ] 阶段七 用户业务
- [ ] 阶段八 统计与上线

## 本地开发（后端）

```bash
cd apps/api
uv venv --python 3.12
uv pip install -e ".[dev]"
.venv/bin/python -m pytest        # 运行测试（SQLite 内存库，无需外部依赖）
```

## 容器部署

```bash
cp .env.example .env              # 修改密钥后
cd infra
docker compose up -d --build      # 自动执行 alembic 迁移 + 初始化默认 admin
```

默认管理员：`admin` / `admin1234`（首次登录后请立即修改）。
