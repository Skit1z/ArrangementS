### 部署更新命令
```bash
ssh aliyun 'cd /opt/ArrangementS && git pull'
# 前端有变更：本地 build 后 tar 推送到 1Panel 的网站目录
cd apps/web && pnpm build
tar -czvf web_dist.tar.gz -C dist .
scp web_dist.tar.gz aliyun:/opt/1panel/www/sites/arrangements/
ssh aliyun 'cd /opt/1panel/www/sites/arrangements && tar -xzvf web_dist.tar.gz -C . && rm web_dist.tar.gz'
# 若有新迁移,api 重启会自动跑 alembic upgrade
ssh aliyun 'systemctl restart arrangements-api arrangements-worker'
```

> **注意：要求 AI 助手在每次修改代码后，都必须走一遍上述部署流程。**
