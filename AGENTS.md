# Agent Guidelines & Rules

## 1. CI Quality Red Line (CI 质量红线) —— 绝对强制

**CI 不通过，严禁 commit，严禁 push。没有例外。**

> **重要提示**：本地必跑项必须与 `.github/workflows/ci.yml` **逐项对齐**。每次修改 CI workflow 时，必须同步更新下方命令列表，**不得遗漏任何一项**。

在进行任何 `git commit` 或 `git push` 操作前，必须先在本地依次执行并通过以下全部校验，**缺一不可**：

### 前端校验（必须全部通过）
```bash
pnpm --filter meeting-scheduler-web typecheck  # TypeScript 类型检查
pnpm --filter meeting-scheduler-web build      # Vite 生产构建
```

### 后端校验（必须全部通过）
```bash
cd apps/api && uv run ruff format --check .   # 格式检查（CI 必跑项，漏掉会被卡！）
cd apps/api && uv run ruff check .            # 代码检查（lint）
cd apps/api && uv run pytest                  # 单元测试
```

### 执行顺序与阻断规则
1. **先跑校验，后 commit** —— 顺序不可颠倒。
2. 上述四项校验中**任何一项**有报错、警告或失败，**立即停止**，禁止执行 `git commit` 和 `git push`。
3. 必须先排查并修复所有问题，直到全部零报错通过后，才允许提交。
4. 不允许 `--no-verify`、`--force` 或任何跳过检查的手段。
5. 不允许仅部分通过就提交（如仅通过前端校验但后端未通过）。

### GitHub Actions 自动部署依赖
- 部署 workflow (`deploy.yml`) 已配置为依赖 CI workflow 完成：仅当 CI 在 `main` 分支上**全部通过**后，才会自动触发部署。
- 手动部署 (`workflow_dispatch`) 不受此限制，但仅限紧急情况使用。
