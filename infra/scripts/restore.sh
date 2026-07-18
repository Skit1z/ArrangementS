#!/bin/sh
# 从 backup.sh 产生的备份包恢复。
#
# 用法：
#   sh /opt/ArrangementS/infra/scripts/restore.sh <backup_tarball>   # 仅解包 + 还原 DB
#   RESTORE_FILES=1 sh /opt/ArrangementS/infra/scripts/restore.sh <backup_tarball>  # 同时还原文件存储
#
# 警告：恢复 DB 会覆盖现有数据。务必先停掉 api/worker，并在测试环境验证后再上生产。
#
# 环境变量：
#   DATABASE_URL           目标库连接串（必填）
#   FILE_STORAGE_PATH      文件存储目录（默认 /var/app/files）
#   RESTORE_FILES          非空时一并解包文件存储
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "用法: sh $0 <backup_tarball> [RESTORE_FILES=1]" >&2
    exit 2
fi

TARBALL="$1"
: "${DATABASE_URL:?DATABASE_URL 必须设置}"
FILE_STORAGE_PATH="${FILE_STORAGE_PATH:-/var/app/files}"
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

echo "[restore] 解包 $TARBALL -> $WORKDIR"
tar -xzf "$TARBALL" -C "$WORKDIR"
INNER=$(ls -d "$WORKDIR"/backup_* | head -1)
if [ -z "$INNER" ] || [ ! -d "$INNER" ]; then
    echo "[restore] 错误：备份包内未找到 backup_* 目录" >&2
    exit 1
fi

# --- 1. 数据库 ---
if [ -f "$INNER/db.sql.gz" ]; then
    PG_URL=$(printf '%s' "$DATABASE_URL" | sed 's|^postgresql+psycopg:|postgresql:|')
    echo "[restore] 恢复 DB（gunzip db.sql.gz | psql $PG_URL）"
    echo "[restore] ⚠️  将覆盖目标库现有数据。5 秒后开始，Ctrl+C 取消。"
    sleep 5
    # 先清空目标库连接对象，再灌入。psql 连接串里库名应指向已存在的空库。
    gunzip -c "$INNER/db.sql.gz" | psql "$PG_URL" >/dev/null
    echo "[restore] DB 恢复完成"
else
    echo "[restore] 跳过 DB：备份内无 db.sql.gz"
fi

# --- 2. 文件存储 ---
if [ -n "${RESTORE_FILES:-}" ] && [ -f "$INNER/files.tar.gz" ]; then
    mkdir -p "$FILE_STORAGE_PATH"
    echo "[restore] 解包文件存储 -> $FILE_STORAGE_PATH"
    tar -xzf "$INNER/files.tar.gz" -C "$(dirname "$FILE_STORAGE_PATH")"
else
    echo "[restore] 跳过文件存储（RESTORE_FILES 未设或备份内无 files.tar.gz）"
fi

# --- 3. 密钥提醒 ---
if [ -f "$INNER/field_encryption_key.txt" ]; then
    echo "[restore] ⚠️  本备份含 FIELD_ENCRYPTION_KEY，请确保运行中的 api 容器使用同一密钥，"
    echo "         否则身份证/银行卡密文将无法解密。密钥文件位于解包目录内。"
fi

echo "[restore] 完成。请重启 api/worker 并核对 /health 与业务数据。"
