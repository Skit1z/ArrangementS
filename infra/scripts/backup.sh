#!/bin/sh
# 数据库 + 文件存储 + 字段加密密钥 备份脚本。
#
# 用法（容器外）：
#   docker compose exec api sh /app/infra/scripts/backup.sh
# 或挂载后在宿主机（需本地有 pg_dump / tar）：
#   sh infra/scripts/backup.sh
#
# 环境变量：
#   DATABASE_URL           postgres 连接串（必填）
#   FILE_STORAGE_PATH      上传文件目录（默认 /var/app/files）
#   FIELD_ENCRYPTION_KEY   字段加密密钥（身份证/银行卡密文恢复必需）
#   BACKUP_DIR             备份输出目录（默认 infra/backup）
#   BACKUP_RETENTION_DAYS  保留天数（默认 30）
#
# 退出码：0 成功；非零失败（set -euo pipefail）。
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL 必须设置}"
FILE_STORAGE_PATH="${FILE_STORAGE_PATH:-/var/app/files}"
BACKUP_DIR="${BACKUP_DIR:-$(cd "$(dirname "$0")/.." && pwd)/backup}"
RETENTION="${BACKUP_RETENTION_DAYS:-30}"
STAMP=$(date +%Y%m%d_%H%M%S)
OUT="$BACKUP_DIR/backup_$STAMP"

mkdir -p "$OUT"

# --- 1. Postgres 逻辑备份 ---
# DATABASE_URL 形如 postgresql+psycopg://user:pass@host:5432/db
# pg_dump 接受 postgresql:// 形式；剥离 +psycopg 即可。
PG_URL=$(printf '%s' "$DATABASE_URL" | sed 's|^postgresql+psycopg:|postgresql:|')
echo "[backup] pg_dump -> $OUT/db.sql.gz"
# PGPASSWORD 让 pg_dump 不交互；连接串里已含密码，但显式更稳
pg_dump "$PG_URL" | gzip > "$OUT/db.sql.gz"

# --- 2. 文件存储（人员 Excel 等上传文件）---
if [ -d "$FILE_STORAGE_PATH" ]; then
    echo "[backup] tar $FILE_STORAGE_PATH -> $OUT/files.tar.gz"
    tar -C "$(dirname "$FILE_STORAGE_PATH")" -czf "$OUT/files.tar.gz" "$(basename "$FILE_STORAGE_PATH")"
else
    echo "[backup] 跳过文件存储：$FILE_STORAGE_PATH 不存在"
fi

# --- 3. 字段加密密钥（离线妥善保管；无此密钥密文不可恢复）---
if [ -n "${FIELD_ENCRYPTION_KEY:-}" ]; then
    printf '%s' "$FIELD_ENCRYPTION_KEY" > "$OUT/field_encryption_key.txt"
    chmod 600 "$OUT/field_encryption_key.txt"
    echo "[backup] 已写入 FIELD_ENCRYPTION_KEY（请将本目录离线保存）"
else
    echo "[backup] 警告：FIELD_ENCRYPTION_KEY 未设置，密文字段将无法从本备份恢复" >&2
fi

# --- 4. 元信息 ---
{
    echo "backup_stamp=$STAMP"
    echo "backup_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "database_url=$DATABASE_URL"
    echo "retention_days=$RETENTION"
} > "$OUT/MANIFEST.txt"

# 打包单文件便于传输
tar -C "$BACKUP_DIR" -czf "$OUT.tar.gz" "backup_$STAMP"
rm -rf "$OUT"
echo "[backup] 完成：$OUT.tar.gz"

# --- 5. 按保留期清理旧备份 ---
echo "[backup] 清理超过 ${RETENTION} 天的旧备份"
find "$BACKUP_DIR" -name 'backup_*.tar.gz' -mtime +"$RETENTION" -print -delete 2>/dev/null || true

echo "[backup] 全部完成"
