# OCAP 架构图与部署架构

## 1. 系统架构图（C4 Container + Deployment）

```mermaid
flowchart TB
    subgraph Users["用户与外部系统"]
        OU[Fab Operator]
        IE[工艺工程师]
        IS[主管/QA]
        IA[系统管理员]
        SPC[外部 SPC]
        FDC[外部 FDC]
        MES[外部 MES]
        APC[外部 APC/Recipe]
        YDMS[外部 YMS/DMS]
    end

    subgraph Edge["接入层"]
        WAF[WAF / 反向代理 nginx]
        LB[L4 LB / DNS RoundRobin]
        GW[API Gateway\nKong / 自研 FastAPI 聚合]
    end

    subgraph App["应用层（无状态横向扩展）"]
        WEB[Uvicorn + Gunicorn OCAP API x N\nFastAPI Async Workers]
        WK[APScheduler Jobs Worker x M\nKPI 聚合 / SLA 升级 / 保留期归档 / 集成拉取]
        STR[Event Stream Consumer x K\nRedis Streams 分发]
    end

    subgraph Service["状态/缓存/消息"]
        RED[(Redis 7 集群<br/>缓存 + RedLock + Streams)]
    end

    subgraph Data["数据层"]
        PG[PostgreSQL 15 主]
        PG_R1[(PostgreSQL 只读副本 #1)]
        PG_R2[(PostgreSQL 只读副本 #2)]
        PGB[PgBouncer 连接池]
    end

    subgraph Storage["对象存储 / 归档"]
        S3[(S3 兼容 MinIO / 云 S3\n报告、附件、备份、冷数据)]
        HIVE[(可选：冷数据分析 Parquet on S3)]
    end

    subgraph Observability["可观测"]
        PROM[Prometheus / VictoriaMetrics]
        GRAF[Grafana 仪表盘]
        LOKI[Loki 日志聚合]
        JAEGER[Jaeger Trace]
    end

    OU & IE & IS & IA --> WAF
    WAF --> LB --> GW --> WEB
    WEB --> PGB --> PG
    WEB --> RED
    WEB --> PGB --> PG_R1 & PG_R2
    WEB --> S3
    WK & STR --> PGB --> PG
    WK & STR --> RED
    SPC & FDC & MES & APC & YDMS --> GW
    WEB & WK & STR -. metrics / logs / traces .-> PROM & LOKI & JAEGER
    PROM --> GRAF
    LOKI --> GRAF
    JAEGER --> GRAF
    PG -. 备份 + WAL 归档 .-> S3
```

## 2. 内部微组件架构（单 Worker 内）

```mermaid
flowchart LR
    REQ[HTTP Request] --> MID[Middleware\nRequest ID / Tenant / Audit / RBAC]
    MID --> DEP[Depends 层 JWT 用户 + 租户 ID]
    DEP --> API[Router/API: 9 个域的路由模块]
    API --> SVC[Application Service: BP-A..I Use Case 编排]
    SVC --> DOM[Domain Model + Domain Service]
    SVC --> EVT[Domain Event Publisher Outbox]
    DOM --> REPO[Repository: SQLAlchemy AsyncSession]
    REPO --> DB[(PostgreSQL)]
    EVT --> OUTBOX[outbox_events 表]
    OUTBOX --> PUMP[Poller → Redis Streams]
    SVC --> INT[Integration Adapter\nHTTP Mock/Real]
    INT --> EXT[SPC/FDC/MES/APC/YMS/DMS]
    SVC --> SEC[Security\nJWT sign/verify + 签名 Hash 链]
    SVC --> CFG[Config + Cache Redis]
    CFG --> R[(Redis)]
```

## 3. 部署架构（macOS 12.7 单机单租户开发/验证）

### 3.1 单机部署拓扑

```mermaid
flowchart LR
    U[浏览器 / curl / Postman] -->|https://localhost:8443| NG[Nginx 1.25\n自签 TLS + 反代]
    NG -->|http://127.0.0.1:8000| APP[Uvicorn 4 worker\n127.0.0.1:8000]
    NG -->|http://127.0.0.1:9001| MIN[MinIO Console]
    APP -->|Unix Socket| PGB[PgBouncer 6432]
    PGB --> PG[(PostgreSQL 15\n5432 仅 127.0.0.1)]
    APP --> RED[Redis 7\n6379 仅 127.0.0.1]
    APP -->|S3 SDK http://127.0.0.1:9000| MIN[MinIO 本地对象存储]
    APP -->|APScheduler 内置 AsyncIOScheduler| APP
    REDIS_VIEW[redis-commander :8081] --> RED
    GRAF[Grafana :3000] -->|DS| PG & RED & M[Prometheus :9090]
```

### 3.2 macOS 12.7 部署步骤（可执行 Plan）

> 目标机：macOS 12.7 Monterey（x86_64 or Apple Silicon），用户 `ocap`，所有依赖用 Homebrew 或官方 pkg 安装。
> 本计划精确到命令级，可脚本化。

#### Step 0. 前置检查与账号
```bash
# 0.1 确认系统版本
sw_vers  # 期望 ProductVersion: 12.7.x
# 0.2 安装 Xcode Command Line Tools
xcode-select --install
# 0.3 创建服务账号（可选，或直接用当前账号）
# sudo sysadminctl -addUser ocap -fullName "OCAP Service" -password <SECURE_PWD> -admin
```

#### Step 1. 安装 Homebrew 与基础依赖
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# 按需追加到 PATH，或在 ~/.zprofile 中
brew install python@3.12 postgresql@15 redis nginx minio/stable/minio pgbouncer prometheus grafana
brew install --cask temurin@17   # 可选：如果未来接 Java 生态的 BPMN 引擎
# 可选开发工具：
brew install jq git curl wget
```

#### Step 2. 启动 PostgreSQL 15 并创建库
```bash
brew services start postgresql@15
# 创建用户与数据库
/usr/local/opt/postgresql@15/bin/createuser -s ocap     # Apple Silicon → /opt/homebrew/opt/...
/usr/local/opt/postgresql@15/bin/createdb -O ocap ocap_db
/usr/local/opt/postgresql@15/bin/createdb -O ocap ocap_test
# 设置密码
/usr/local/opt/postgresql@15/bin/psql -d postgres -c "ALTER USER ocap PASSWORD 'STRONG_PG_PWD_CHANGE_ME';"
# 初始化扩展
/usr/local/opt/postgresql@15/bin/psql -U ocap -d ocap_db -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
/usr/local/opt/postgresql@15/bin/psql -U ocap -d ocap_db -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
```

#### Step 3. 启动 Redis
```bash
brew services start redis
# 给 Redis 加密码
redis-cli CONFIG SET requirepass "STRONG_REDIS_PWD_CHANGE_ME"
# 持久化保存
redis-cli CONFIG REWRITE
```

#### Step 4. 配置并启动 PgBouncer（可选但推荐）
```bash
mkdir -p /usr/local/var/pgbouncer /usr/local/etc
cat > /usr/local/etc/pgbouncer.ini <<'EOF'
[databases]
ocap_db = host=127.0.0.1 port=5432 dbname=ocap_db
ocap_test = host=127.0.0.1 port=5432 dbname=ocap_test
[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
auth_type = md5
auth_file = /usr/local/etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 500
default_pool_size = 32
EOF
cat > /usr/local/etc/pgbouncer/userlist.txt <<'EOF'
"ocap" "md5$(echo -n 'STRONG_PG_PWD_CHANGE_MEocap' | md5 -q)"
EOF
# pgbouncer 启动：macOS 无 brew formula 服务，可手动或 launchd（见后）
```

#### Step 5. 安装 OCAP 代码与 Python 依赖
```bash
cd /opt
sudo mkdir -p ocap && sudo chown $(whoami):staff /opt/ocap
cd /opt/ocap
git clone <PRIVATE_OR_PUBLIC_REPO_URL> app
cd app
# 代码也可直接用本仓库：ocap_py
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install poetry
poetry install --no-dev --no-interaction
# 如果不想用 poetry：
#   poetry export -f requirements.txt --output requirements.txt --without-hashes
#   pip install -r requirements.txt
```

#### Step 6. 环境变量配置 `/opt/ocap/app/.env`
```bash
cat > /opt/ocap/app/.env <<'EOF'
# 应用
APP_ENV=production
APP_NAME=ocap
DEBUG=false
SECRET_KEY=change_me_strong_random_64bytes_please_use_openssl_rand_hex_64
BASE_URL=https://localhost:8443
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY_PEM_PATH=/opt/ocap/app/config/jwt_private.pem
JWT_PUBLIC_KEY_PEM_PATH=/opt/ocap/app/config/jwt_public.pem
JWT_ACCESS_TTL_SECONDS=3600
JWT_REFRESH_TTL_SECONDS=604800

# 数据库
DATABASE_URL=postgresql+asyncpg://ocap:STRONG_PG_PWD_CHANGE_ME@127.0.0.1:6432/ocap_db
TEST_DATABASE_URL=sqlite+aiosqlite:///:memory:?cache=shared

# Redis
REDIS_URL=redis://:STRONG_REDIS_PWD_CHANGE_ME@127.0.0.1:6379/0

# 对象存储（MinIO 本地）
S3_ENDPOINT_URL=http://127.0.0.1:9000
S3_BUCKET=ocap
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_REGION=us-east-1
S3_SECURE=false

# 集成（mock 模式）
INTEGRATION_DEFAULT_MODE=mock
# MES_BASE_URL / SPC_BASE_URL 等真实模式按需填写
EOF
```
生成 JWT 密钥（RS256）：
```bash
mkdir -p /opt/ocap/app/config
cd /opt/ocap/app/config
openssl genrsa -traditional -out jwt_private.pem 2048
openssl rsa -in jwt_private.pem -pubout > jwt_public.pem
chmod 600 jwt_private.pem
```

#### Step 7. 迁移 + 打底数据
```bash
cd /opt/ocap/app
source .venv/bin/activate
# alembic 迁移
alembic upgrade head
# 打底 seed 数据（租户/用户/角色/权限/集成 mock store）
python -m app.db.seed.loader
# 创建 1 个默认管理员（首次）
python -m app.scripts.create_admin --username admin --password Admin123! --tenant fab_a --email admin@fab.local
```

#### Step 8. MinIO 启动 + 建桶
```bash
# 推荐用 launchd 托管；临时手动：
mkdir -p /opt/ocap/minio-data
export MINIO_ROOT_USER=minioadmin
export MINIO_ROOT_PASSWORD=minioadmin
# /opt/homebrew/bin/minio server --address 127.0.0.1:9000 --console-address 127.0.0.1:9001 /opt/ocap/minio-data &
# 建桶
curl -L -o /usr/local/bin/mc https://dl.min.io/client/mc/release/darwin-amd64/mc && chmod +x /usr/local/bin/mc
mc alias set local http://127.0.0.1:9000 minioadmin minioadmin
mc mb local/ocap --ignore-existing
mc anonymous set download local/ocap  # 如需要公开下载；默认私有更好
```

#### Step 9. Nginx 反代 + TLS
```bash
# 生成自签证书
mkdir -p /opt/ocap/nginx/tls
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
   -keyout /opt/ocap/nginx/tls/localhost.key \
   -out /opt/ocap/nginx/tls/localhost.crt \
   -subj "/CN=localhost"
# 写 nginx.conf 片段并 include 进 brew 的 nginx
# /usr/local/etc/nginx/servers/ocap.conf（Intel）或 /opt/homebrew/etc/nginx/servers/ocap.conf（ARM）
cat > /usr/local/etc/nginx/servers/ocap.conf <<'EOF'
server {
  listen 8443 ssl http2;
  server_name localhost;
  ssl_certificate      /opt/ocap/nginx/tls/localhost.crt;
  ssl_certificate_key  /opt/ocap/nginx/tls/localhost.key;
  client_max_body_size 64m;

  location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
  }
  location /docs { proxy_pass http://127.0.0.1:8000; }
  location /openapi.json { proxy_pass http://127.0.0.1:8000; }
  location /redoc { proxy_pass http://127.0.0.1:8000; }
  location /minio/ {
    proxy_pass http://127.0.0.1:9001/;
  }
  location /grafana/ {
    proxy_pass http://127.0.0.1:3000/;
  }
}
EOF
# 语法检查
nginx -t
brew services restart nginx
```

#### Step 10. 启动 OCAP 应用（Uvicorn 多 worker + Gunicorn）
```bash
cd /opt/ocap/app && source .venv/bin/activate
gunicorn app.main:app -k uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8000 --workers 4 --threads 4 \
  --timeout 60 --max-requests 5000 --max-requests-jitter 500 \
  --chdir /opt/ocap/app
# 或直接写 launchd plist，见 Step 11
```

#### Step 11. macOS launchd 系统服务（开机自启）

将以下模板 4 份分别保存为：
- `/Library/LaunchDaemons/com.fab.ocap.app.plist`
- `/Library/LaunchDaemons/com.fab.ocap.pgbouncer.plist`
- `/Library/LaunchDaemons/com.fab.ocap.minio.plist`
- `/Library/LaunchDaemons/com.fab.ocap.jobs.plist`（仅 APScheduler worker）

示例：`com.fab.ocap.app.plist`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.fab.ocap.app</string>
  <key>UserName</key><string>ocap</string>
  <key>WorkingDirectory</key><string>/opt/ocap/app</string>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/opt/ocap/app/.venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
  <key>ProgramArguments</key><array>
    <string>/opt/ocap/app/.venv/bin/gunicorn</string>
    <string>app.main:app</string>
    <string>-k</string><string>uvicorn.workers.UvicornWorker</string>
    <string>--bind</string><string>127.0.0.1:8000</string>
    <string>--workers</string><string>4</string>
    <string>--timeout</string><string>60</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/var/log/ocap/app.stdout.log</string>
  <key>StandardErrorPath</key><string>/var/log/ocap/app.stderr.log</string>
</dict></plist>
```
安装 & 启动：
```bash
sudo mkdir -p /var/log/ocap && sudo chown ocap:staff /var/log/ocap
sudo launchctl load -w /Library/LaunchDaemons/com.fab.ocap.app.plist
```

#### Step 12. 验证部署
```bash
# 1. HTTPS API 健康
curl -k https://localhost:8443/healthz
# → {"status":"ok","version":"..."}
# 2. 登录拿 token
TOKEN=$(curl -k -X POST https://localhost:8443/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"tenant_code":"fab_a","username":"admin","password":"Admin123!"}' \
  | jq -r .access_token)
# 3. 查事件
curl -k -H "Authorization: Bearer $TOKEN" "https://localhost:8443/api/v1/triggers/events?page_size=5"
# 4. OpenAPI 页面
open "https://localhost:8443/docs"
# 5. 全量冒烟测试（pytest 用真实 HTTP）
cd /opt/ocap/app && source .venv/bin/activate
pytest tests/smoke/ --base-url https://localhost:8443 --token "$TOKEN" -v
```

#### Step 13. Prometheus + Grafana（可观测可选）
```bash
brew services start prometheus
brew services start grafana
# Prometheus 默认 http://127.0.0.1:9090，Grafana 默认 http://127.0.0.1:3000（admin/admin）
# 导入 ID：1860 Node Exporter + 自定义 OCAP API 指标（若暴露 /metrics）
```

---

## 4. 进程端口矩阵（macOS 单机）

| 组件 | 监听地址 | 端口 | 协议 | 外网暴露 |
| --- | --- | --- | --- | --- |
| OCAP API（Uvicorn） | 127.0.0.1 | 8000 | HTTP | 否（经 Nginx） |
| Nginx TLS | 0.0.0.0 | 8443 | HTTPS | 是 |
| PostgreSQL 15 | 127.0.0.1 | 5432 | PG | 否 |
| PgBouncer | 127.0.0.1 | 6432 | PG | 否 |
| Redis 7 | 127.0.0.1 | 6379 | Redis | 否 |
| MinIO S3 API | 127.0.0.1 | 9000 | HTTP | 否 |
| MinIO Console | 127.0.0.1 | 9001 | HTTP | 经 Nginx /minio/ |
| Prometheus | 127.0.0.1 | 9090 | HTTP | 否 |
| Grafana | 127.0.0.1 | 3000 | HTTP | 经 Nginx /grafana/ |

## 5. 数据备份与恢复（macOS）

```bash
# 每日 02:00 全量 pgBackRest / pg_dump（轻量用 pg_dump），launchd 或 cron
cat > /opt/ocap/scripts/backup.sh <<'EOF'
#!/bin/bash
set -euo pipefail
TS=$(date +%Y%m%d_%H%M%S)
OUT=/opt/ocap/backups
mkdir -p "$OUT"
/usr/local/opt/postgresql@15/bin/pg_dump -U ocap -Z 9 -F c -f "$OUT/ocap_db_${TS}.dump" ocap_db
aws --endpoint-url http://127.0.0.1:9000 s3 cp "$OUT/ocap_db_${TS}.dump" s3://ocap-backups/
find "$OUT" -type f -name "*.dump" -mtime +14 -delete
EOF
chmod 700 /opt/ocap/scripts/backup.sh
# crontab -e 或者 launchd
# 0 2 * * * /opt/ocap/scripts/backup.sh >> /var/log/ocap/backup.log 2>&1

# 恢复演练（每月一次）
# pg_restore -U ocap -d ocap_test --no-owner -j 4 backups/ocap_db_YYYYMMDD_HHMMSS.dump
```

---

## 6. 故障转移（单机）

单机无可切换节点，但提供：
- PostgreSQL `WAL 归档` + `PITR` 回到 15 分钟内任意点
- 应用进程：launchd 自动重启（KeepAlive=true）
- Redis：RDB + AOF 持久化，brew services 重启
- 数据备份外挂硬盘冗余

---

## 7. 部署校验清单（Go-Live Checklist）

- [ ] macOS 12.7 所有安全补丁已更新（软件更新）
- [ ] 文件保险箱 FileVault 开启（整机磁盘加密）
- [ ] PostgreSQL 仅 127.0.0.1，`pg_hba.conf` 禁止外部
- [ ] Redis `requirepass` 已设，绑定 127.0.0.1
- [ ] JWT 私钥权限 600，备份离线保存
- [ ] MinIO 强密码 + 桶访问策略
- [ ] Nginx 仅暴露 8443，防火墙（pf 或 Murus / Little Snitch）
- [ ] `.env` 文件 600，不可写非服务账户
- [ ] 审计日志目录轮转（newsyslog / logrotate）
- [ ] 备份脚本每日执行已验证一次还原
- [ ] 管理员密码强度 ≥ 16 位，MFA 建议（未来加 OAuth2 / OIDC）
- [ ] 冒烟 + E2E 测试通过
