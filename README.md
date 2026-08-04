# OCAP (Out-of-Control Action Plan) System

> 半导体制造领域 **异常失控处置计划 (OCAP)** 系统 —— 对标应用材料 (Applied Materials) SmartFactory Knowledge Advisor，面向晶圆厂工程智能 (EI) 场景，构建自动化、集成化、低人为错误的异常处置闭环。

## ⚠️ 概念澄清

本项目的 **OCAP** 指 **Out-of-Control Action Plan（失控处置计划）**，属于半导体制造 CIM/EI 领域概念，**与有线电视交互标准 OpenCable Application Platform 毫无关系**。

---

## 🎯 项目定位与设计目标

OCAP 系统围绕工厂 **工程智能 (Engineering Intelligence, EI)** 系统展开，以三大设计目标为核心：

- **自动化 (Automation)**：异常触发 → 排查 → 处置 → 跟踪的全流程自动化
- **集成化 (Integration)**：打通 SPC / FDC / APC / Recipe 等系统数据孤岛
- **减少人为错误 (Reduce Human Error)**：通过标准化流程降低人为变异性

> 行业痛点：据应用材料资料，工厂近 **50% 的报废** 由人为错误造成，OCAP 旨在系统性解决该问题。

---

## 🛠️ 技术栈

| 分类 | 技术选型 | 说明 |
| :--- | :--- | :--- |
| 语言 | Python 3.12+ | 主开发语言（PEP 695 / match-case） |
| 构建/依赖 | Poetry | 依赖管理与打包 |
| Web 框架 | FastAPI 0.110 + Starlette | 高性能异步 + 自动 OpenAPI |
| 测试框架 | pytest + pytest-asyncio + httpx | SQLite :memory: 单测 0 外部依赖 |
| 数据库 | PostgreSQL 15 | JSONB / BRIN / 分区表 |
| ORM | SQLAlchemy 2.x Async + Alembic | ORM 与数据库迁移（含 JSONBCompat 跨 PG/SQLite） |
| 安全 | python-jose + passlib[pbkdf2_sha256] + JWT RS256 | 21 CFR Part 11 合规 |
| 缓存/锁/流 | Redis 7 | Redlock 分布式锁 / Streams 事件总线 |
| 调度 | APScheduler AsyncIOScheduler | KPI 聚合 / SLA 升级 / 保留期归档 |
| 对象存储 | MinIO / S3 兼容 | 备份 / 报告 / 归档分区 |
| 文档 | Mermaid 内嵌 Markdown | 架构 / ER / 数据流可渲染图 |

---

## 📋 核心功能列表 (Core Functions)

### 1. 异常检测与触发

| 功能点 | 说明 |
| :--- | :--- |
| **集成 SPC 触发** | 与 SPC（统计过程控制）应用紧密集成，当控制图出现 OOC（Out-of-Control）时自动触发 OCAP 流程 |
| **集成 FDC 触发** | 与 FDC（故障检测与分类）应用紧密集成，当设备或过程异常时自动触发 OCAP 流程 |
| **多源触发支持** | 支持人工触发、定时触发、外部系统事件触发等多种触发方式 |
| **触发规则配置** | 可配置触发阈值、触发条件、触发优先级 |

### 2. 自动化工作流引擎

| 功能点 | 说明 |
| :--- | :--- |
| **引导式故障排查** | 通过集成的工作流引擎，自动化信息流帮助用户排查 SPC 和 FDC 违规的潜在原因 |
| **标准操作步骤 (SOP)** | 引导用户执行标准操作步骤，确保排查过程规范化 |
| **工作流编排** | 支持串行、并行、分支、循环等多种工作流编排模式 |
| **动态决策树** | 基于排查结果动态调整后续步骤，支持决策树形态的排查路径 |
| **可配置流程模板** | 支持按工序、设备、异常类型配置不同的 OCAP 流程模板 |

### 3. 减少人为错误

| 功能点 | 说明 |
| :--- | :--- |
| **标准化流程** | 通过标准化流程减少因错误解释因果关系而导致的人为变异性 |
| **强制校验** | 关键操作步骤强制校验，防止跳步、漏步 |
| **电子签核** | 关键处置动作支持电子签核，确保可追溯 |
| **知识沉淀** | 历史处置经验沉淀为知识库，避免重复犯错 |

### 4. 数据集成与生态

| 功能点 | 说明 |
| :--- | :--- |
| **E3 系列数据整合** | 可容纳来自 APC、SPC、FDC、配方管理等系统的数据 |
| **打破数据孤岛** | 提供完整的异常解决视图，跨系统数据关联 |
| **开放集成接口** | 提供标准 REST API 与消息队列接口，支持与第三方系统集成 |
| **SEMI 标准对接** | 对接 SEMI E30 (GEM) / E37 (HSMS) / E87 (CMS) / E90 (STC) / E94 / E116 (EDA) 等标准 |

### 5. 行动与跟踪管理

| 功能点 | 说明 |
| :--- | :--- |
| **行动计划制定** | 支持用户制定解决异常的行动计划 |
| **行动跟踪** | 管理行动执行状态，跟踪进度直至闭环 |
| **历史活动识别** | 识别以往的故障排除活动，避免重复劳动 |
| **SLA 管理** | 行动项支持 SLA 配置与超时预警 |
| **闭环验证** | 处置完成后支持效果验证，确保异常真正消除 |

### 6. 高级分析

| 功能点 | 说明 |
| :--- | :--- |
| **上下文模式匹配 (CPM)** | 在工作流中嵌入 CPM，基于历史相似案例辅助决策 |
| **AI 辅助决策** | 嵌入 AI 功能，辅助用户进行更智能的决策 |
| **根因分析 (RCA)** | 基于数据和规则辅助根因分析 |
| **趋势分析** | 异常趋势统计分析，支持持续改进 |

### 7. 合规与审计

| 功能点 | 说明 |
| :--- | :--- |
| **GEP 合规** | 引导用户遵循良好工程实践 (Good Engineering Practice) |
| **审计追溯** | 符合企业和行业质量审计标准，全链路操作可审计 |
| **SPC 控制图规范** | 对 SPC 控制图限制和样本注释进行规范性管理 |
| **电子记录合规** | 符合 21 CFR Part 11 电子记录/电子签名要求 |

---

## 📦 非核心/辅助功能 (Non-Core / Peripheral Functions)

### 1. 与其他系统的集成层

作为 CIM 生态系统的一部分，通过集成层与以下系统协同工作，以缩短从"发现问题到解决问题" (G2G, Gate-to-Gate) 的时间：

- **AMS (Alarm Management System)**：报警管理系统
- **SFMM (SmartFactory Maintenance Management)**：设备维护管理系统
- **MES (Manufacturing Execution System)**：制造执行系统
- **YMS (Yield Management System)**：良率管理系统
- **DMS (Defect Management System)**：缺陷管理系统

> 这更多是平台层面的协作，而非 OCAP 本身的直接功能。

### 2. 依托于 SmartFactory 平台

- Knowledge Advisor 是应用材料 SmartFactory 自动化解决方案的一个组成部分
- 该平台已服务半导体行业超过 30 年
- 其功能价值很大程度上依托于整个平台的成熟度和广泛的应用基础

---

## 🚀 快速开始

> 详细的业务点对标请参见 [docs/BUSINESS_POINTS.md](docs/BUSINESS_POINTS.md)
> 设计文档（9 份 + Mermaid 图）见 [docs/design/](docs/design/)：
>
> 01 [概要设计](docs/design/01-hld-architecture.md) · 02 [功能设计](docs/design/02-functional-design.md) · 03 [用例图](docs/design/03-use-case.md) · 04 [数据流图](docs/design/04-data-flow-diagram.md)
> 05 [数据库设计](docs/design/05-database-design.md) · 06 [容量/性能](docs/design/06-performance-capacity.md) · 07 [HTTP API](docs/design/07-http-api-design.md)
> 08 [架构与部署](docs/design/08-architecture-deployment.md) · 09 [测试方案](docs/design/09-testing-plan.md)

```bash
# 1. 安装依赖
poetry install

# 2. 拷贝环境变量模板
cp .env.example .env
# 按需配置 DATABASE_URL / REDIS_URL / JWT 密钥（开发模式可直接保持默认：SQLite 内存）

# 3. 运行全量单元 + 集成测试（0 外部依赖）
poetry run pytest tests/ -q

# 4. 启动开发服务（http://127.0.0.1:8000/docs 查看 OpenAPI）
poetry run uvicorn app.main:app --reload
```

## 🧪 测试矩阵与覆盖（当前实现）

```
tests/unit/        186 tests    单测：9 个 BP 域 + core + seed + auth + health
tests/integration/   2 tests    端到端 E2E：主链路覆盖 BP-A/B/C/D/E/F/G/H/I
合计                 188 tests  全部通过（SQLite 内存 0 外部依赖）
```

关键实现亮点（代码与设计 1:1 对应）：

| 设计点 | 代码位置 | 说明 |
| --- | --- | --- |
| DDD 分层 9 域聚合 | `app/domains/{trigger,workflow,rca,action,integration,knowledge,analytics,compliance,iam}` + platform | 每域 `models/schemas/service/api` 四件套 |
| 嵌入 BPMN-lite 引擎 | `app/workflow_engine/` | compiler / engine / expressions / visualizer |
| 跨 PG + SQLite JSONB 兼容 | `app/core/types.py::JSONBCompat`（TypeDecorator） | 单测 SQLite / 生产 PG，同一套代码 |
| 乐观并发控制 | `app/db/base.py::VersionMixin` + workflow advance 重试 | |
| 21 CFR Part 11 电子签名 Hash 链 | `app/domains/action/service.py::_compute_signature_hash` | prev_hash → record_hash 双链 |
| 审计链 Hash 链 | `app/domains/compliance/models.py::AuditLog` + verify API | 双链 + 只追加 |
| CPM 上下文模式匹配 RCA 推荐 | `app/domains/rca/service.py::_score_context` | 10 特征加权打分 |
| 知识图谱实体/关系/路径 | `app/domains/knowledge/models.py` + API | nodes / edges / paths 三模型 |
| 9 个三方系统 Mock 客户端 | `app/integrations/fake/{spc,fdc,mes,apc,yms,dms,ams,sfmm,recipe}.py` + store | 本地测试真实业务数据打底 |
| 幂等 Seed 加载（10 份 YAML） | `app/db/seed/loader.py` | 版本控制、重复加载无副作用 |
| macOS 12.7 单机部署 Step-by-Step | `docs/design/08-architecture-deployment.md` | Homebrew 一键 + launchd plist 模板 |

---

## 📂 项目结构

```
ocap_py/
├── app/
│   ├── api/v1/                   # 路由入口：auth + health
│   ├── core/                     # config / deps / exceptions / pagination / security / types
│   ├── db/
│   │   ├── base.py               # Base + ID/Tenant/Timestamp/Version Mixin
│   │   ├── session.py            # AsyncSession 工厂（PG/SQLite 自动）
│   │   └── seed/                 # 10 份 seed YAML + 幂等 loader
│   ├── domains/                  # DDD 9 域（BP-A~I），每域 models/schemas/service/api
│   ├── integrations/             # 三方集成：base / dtos / registry / fake(9 个)
│   ├── workflow_engine/          # BPMN-lite 引擎（编译/执行/表达式/可视化）
│   └── main.py                   # FastAPI app factory + lifespan + 路由注册
├── tests/
│   ├── conftest.py               # db_session / authed_client / admin_client / seed_data / mock_store
│   ├── unit/                     # 单测 186
│   └── integration/              # E2E 主链路 2 条
├── docs/
│   ├── BUSINESS_POINTS.md        # 业务点 9 大类完整对标
│   └── design/                   # 9 份设计文档 + Mermaid 图
├── alembic.ini                   # （可选：Alembic 迁移入口）
├── pyproject.toml                # Poetry 依赖 + pytest/ruff 配置
├── .env.example                  # 环境变量模板
└── README.md
```

---

## 🖥️ macOS 12.7 单机一键部署（开发验证 / 单租户基线）

完整 13 步（PG15 / Redis7 / Nginx / MinIO / PgBouncer / Prometheus / Grafana / launchd），见：
👉 [docs/design/08-architecture-deployment.md Step 0~13](docs/design/08-architecture-deployment.md#3-部署架构macos-127-单机单租户开发验证)

最小化快速验证（不装任何外部服务，0 依赖）：
```bash
poetry install
DATABASE_URL="sqlite+aiosqlite:///:memory:?cache=shared" \
INTEGRATION_DEFAULT_MODE=mock \
poetry run pytest tests/ -q
# → 188 passed
```

---

## 📚 参考资料

- Applied Materials SmartFactory Knowledge Advisor 官方资料
- SEMI 标准系列 (E10, E30, E37, E87, E90, E94, E116, E122, E124, E125, E164 等)
- ISA-95 企业-控制系统集成标准
- IRDS 国际器件与系统路线图

---

## 📄 License

MIT
