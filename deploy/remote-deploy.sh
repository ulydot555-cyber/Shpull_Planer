#!/usr/bin/env bash
set -euo pipefail

DEPLOY_PATH="${DEPLOY_PATH:-/root/soft_blue_planner_crud}"
SERVICE_NAME="${SERVICE_NAME:-soft-blue-planner}"
RELEASE_ARCHIVE="/tmp/soft-blue-planner-release.tar.gz"
BACKUP_DIR="/root/soft_blue_planner_backups"

mkdir -p "$DEPLOY_PATH" "$BACKUP_DIR"

if [ -f "$DEPLOY_PATH/planner.db" ]; then
    cp "$DEPLOY_PATH/planner.db" "$BACKUP_DIR/planner-$(date +%Y%m%d-%H%M%S).db"
fi

shopt -s dotglob nullglob
for item in "$DEPLOY_PATH"/*; do
    case "$(basename "$item")" in
        .venv|planner.db)
            continue
            ;;
    esac
    rm -rf "$item"
done
shopt -u dotglob nullglob

tar -xzf "$RELEASE_ARCHIVE" -C "$DEPLOY_PATH"
rm -f "$RELEASE_ARCHIVE"

cd "$DEPLOY_PATH"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

systemctl restart "$SERVICE_NAME"
systemctl is-active --quiet "$SERVICE_NAME"
