# 会议场地排班管理系统 (ArrangementS)

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React-61DAFB?style=flat-square&logo=react)](https://reactjs.org/)
[![OR-Tools](https://img.shields.io/badge/Solver-OR--Tools-4285F4?style=flat-square&logo=google)](https://developers.google.com/optimization)
[![Build Status](https://img.shields.io/badge/Build-Success-success?style=flat-square)](#)

> **党政办公室会议场地排班管理系统** 是一套专为党政办会议场地值班、加班以及日常排班管理设计的全栈解决方案。系统基于 Google OR-Tools CP-SAT 约束规划求解器实现多维公平目标的自动化排班，整合了教务系统课表 PDF 解析、请假与换班生命周期审核、实时工时审计统计以及移动端/PC端协同功能。目前已完成全系统审计复核及测试验证，正式进入生产上线阶段。

---

## 🌟 核心特性

1. **智能自动化排班 (OR-Tools CP-SAT)**
   - **多维公平目标**：统筹周末班次、早晚班、多场地活跃度等多维度公平度，避免特定人员过度排班。
   - **严密的约束校验**：全面覆盖资格审查、时间重叠、假期冲突、每周工时上限（覆盖拖拽、手动、替班、换班等全流程）。
   - **生成与发布机制**：草稿支持智能重生成并自动保留手动添加的岗位与分配；支持多版本迭代与自动递增修订号。

2. **教务课表智能解析**
   - 支持直接上传本校教务系统导出的 PDF 格式课表。
   - 基于 PyMuPDF 智能提取周次、节次、教学楼等关键信息，并支持在前端直接进行可视化编辑（增删改课程时段）。
   - 自动生成精确到具体周次的“不可值班区间”，自动规避上课时间。

3. **全生命周期的审核中心**
   - **请假与空缺**：请假批准后，对应班次自动标记为空缺，工时清零，且原人员自动在周表和个人日程中隐藏。
   - **换班与替班**：支持指定人换班与公开替班报名；终审时系统会自动校验双方每周工时上限并返回实名候选人白名单。
   - **考勤与未到岗**：支持一键操作“完成”与“未到岗”，直接扣减或记录实际工时，自动写回审计日志。

4. **多维度工时审计与统计**
   - 实时计算平衡工时、实际工时以及分场地动态统计。
   - 支持锁定特定周/月的统计数据，防止历史数据被误重算。
   - 提供标准 Excel 导出功能（自动过滤敏感信息），符合政企审计规范。

---

## 🏗️ 系统架构

```
                     ┌──────────┐
       :80/:443 ───▶ │ 1Panel   │── /api/*,/health ──┐
                     │OpenResty │                     ▼
                     │ + SPA静态 │              ┌──────────┐
                     └──────────┘              │   api    │ FastAPI / uvicorn
                                               │ (自动迁移) │
                                               └────┬─────┘
                                                    │
                       ┌──────────┐                 │
                       │  worker  │◀────────────────┤  共享 Postgres
                       │APScheduler│                │
                       │ 周期任务  │                │
                       └──────────┘
                      ┌───────────┐
                      │  postgres │
                      └───────────┘
```

---

## 📂 仓库目录结构

```bash
ArrangementS/
├── apps/
│   ├── api/                   # FastAPI 后端服务
│   │   ├── app/
│   │   │   ├── api/           # RESTful 接口 (v1)
│   │   │   ├── models/        # SQLAlchemy 2.0 数据模型
│   │   │   ├── schemas/       # Pydantic 2.0 数据验证
│   │   │   ├── scheduling/    # OR-Tools 排班核心算法及约束条件
│   │   │   ├── services/      # 核心业务逻辑服务
│   │   │   └── tasks/         # APScheduler 周期任务
│   │   └── tests/             # 后端单元与集成测试 (pytest)
│   └── web/                   # React + Vite 前端 SPA
│       ├── src/
│       │   ├── components/    # 共享 UI 组件
│       │   ├── features/      # 业务特性模块 (API 交互及状态管理)
│       │   └── pages/         # 页面视图 (含管理端与用户端)
├── infra/                     # 基础设施配置
│   ├── scripts/               # 备份、恢复与运维脚本
│   └── systemd/               # Systemd 服务配置文件
└── docs/                      # 系统设计、部署及审计文档
    ├── acceptance/            # 验收报告与复核记录
    ├── api/                   # 接口定义文档
    └── database/              # 数据库设计及变更记录
```

---

## ⚙️ 快速开始

### 1. 后端本地开发环境

系统后端推荐使用高效的 Python 包管理工具 `uv` 进行依赖管理。

```bash
# 1. 进入后端目录
cd apps/api

# 2. 创建并激活虚拟环境 (需 Python 3.12)
uv venv --python 3.12
source .venv/bin/activate  # macOS/Linux

# 3. 安装依赖（包含开发依赖）
uv pip install -e ".[dev]"

# 4. 配置环境变量
cp .env.example .env
# 根据本地环境修改 .env（例如数据库连接、加解密密钥等）

# 5. 运行数据库迁移与初始化数据
uv run alembic upgrade head

# 6. 运行后端服务
uv run uvicorn app.main:app --reload --port 8000

# 7. 运行单元测试
uv run pytest
```

### 2. 前端本地开发环境

前端采用 React + Vite 开发，推荐使用 `pnpm` 作为包管理器。

```bash
# 1. 进入前端目录
cd apps/web

# 2. 安装依赖
pnpm install

# 3. 运行本地开发服务 (默认代理 /api 至 http://localhost:8000)
pnpm dev

# 4. 运行前端检查与生产构建
pnpm typecheck
pnpm test
pnpm build
```

---

## 🚀 生产部署与日常运维

完整的生产部署采用 **Systemd 托管服务 + 1Panel OpenResty 反向代理与静态托管** 的极简方案。详见 [部署与操作手册](file:///Users/skit1z/WorkSpace/ArrangementS/docs/deployment.md)。

### 1. 日常升级流程

当代码库更新时，可以通过以下步骤完成平滑升级：

```bash
# 1. 登录服务器拉取最新代码
ssh aliyun 'cd /opt/ArrangementS && git pull'

# 2. 重启后端及 Worker 服务（API 服务启动时会自动执行 alembic 数据库迁移）
ssh aliyun 'systemctl restart arrangements-api arrangements-worker'

# 3. 本地构建前端静态文件并推送部署至 1Panel 静态目录
cd apps/web && pnpm build
tar -czvf web_dist.tar.gz -C dist .
scp web_dist.tar.gz aliyun:/opt/1panel/www/sites/arrangements/
ssh aliyun 'cd /opt/1panel/www/sites/arrangements && tar -xzvf web_dist.tar.gz -C . && rm web_dist.tar.gz'
```

### 2. 周期任务 (arrangements-worker)

后台周期任务基于 APScheduler 独立进程运行，配置为 `arrangements-worker.service`，主要负责以下自动化逻辑：
- **每 5 分钟**：自动完成已到结束时间的排班班次，将状态置为 `已完成`（`auto_complete_after_end`）。
- **每日 02:00 UTC (10:00 CST)**：自动检查并失效过期学期的课程表及不可值班区间，将学期状态重置。

### 3. 数据备份与灾难恢复

系统涉及敏感个人数据（如身份证、银行卡号等），所有敏感字段均采用 AES-256 加密存储在数据库中。**请务必妥善保管密钥。**

#### 💾 自动/手动备份
系统自带 `infra/scripts/backup.sh` 脚本，可同时备份 **PostgreSQL 结构与数据、上传的课表/人员文件** 以及 **数据库字段加密密钥 (`FIELD_ENCRYPTION_KEY`)**。

建议配置 `cron` 每天凌晨执行备份：
```bash
0 3 * * * sh /opt/ArrangementS/infra/scripts/backup.sh >> /var/log/scheduler-backup.log 2>&1
```

> [!WARNING]
> 备份包内含解密敏感字段必需的 `FIELD_ENCRYPTION_KEY`。请将备份包定期归档到离线或异地安全存储介质，切勿与代码仓库同存。

#### 🔄 灾难恢复
如遇硬件故障或误操作，可按以下步骤快速恢复：
```bash
# 1. 停止相关服务，防止恢复期间数据写入冲突
systemctl stop arrangements-api arrangements-worker

# 2. 执行恢复脚本（覆盖现有数据库并还原静态文件）
RESTORE_FILES=1 sh /opt/ArrangementS/infra/scripts/restore.sh /opt/ArrangementS/infra/backup/backup_YYYYMMDD_HHMMSS.tar.gz

# 3. 检查并确保 /opt/ArrangementS/.env 中的 FIELD_ENCRYPTION_KEY 与备份中一致

# 4. 重启服务并检查健康状态
systemctl start arrangements-api arrangements-worker
curl -fsS http://localhost:8000/health
```

---

## 🔒 安全与审计规范

1. **核心敏感字段加密**：用户的银行卡号、身份证号等信息在落库时通过 `FIELD_ENCRYPTION_KEY` 进行对称加密，即使数据库被还原，脱离了配置密钥明文信息也不会泄露。
2. **全局审计日志**：系统对所有关键操作（如手动调整排班、换班终审、请假批准、手动确认完成等）均记录完整的审计日志（操作人、时间、变更前后的差异），便于事后追溯。
3. **API 安全鉴权**：接口采用 JWT 双 Token 刷新机制，遵循严格的 RBAC 角色权限控制（Admin / Staff / User），保证非授权操作被有效拦截。
