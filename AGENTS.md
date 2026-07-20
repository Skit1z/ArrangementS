# Agent Guidelines & Rules

## 1. CI Quality Red Line (CI 质量红线)
- **CI 不通过严禁提交**：在进行任何 `git commit` 或 `git push` 操作前，必须先在本地运行并通过所有 CI 关联的校验（包括前端类型检查与构建 `pnpm --filter meeting-scheduler-web typecheck && pnpm --filter meeting-scheduler-web build`，以及后端代码检查与单元测试 `cd apps/api && uv run ruff check . && uv run pytest`）。
- 若上述任何一项校验存在报错或失败，**绝对不允许提交或推送代码**，必须先排查修复至全量通过后方可提交。

<claude-mem-context>
# Memory Context

# claude-mem status

This project has no memory yet. The current session will seed it; subsequent sessions will receive auto-injected context for relevant past work.

Memory injection starts on your second session in a project.

`/learn-codebase` is available if the user wants to front-load the entire repo into memory in a single pass (~5 minutes on a typical repo, optional). Otherwise memory builds passively as work happens.

Live activity: http://localhost:37701
How it works: `/how-it-works`

This message disappears once the first observation lands.
</claude-mem-context>