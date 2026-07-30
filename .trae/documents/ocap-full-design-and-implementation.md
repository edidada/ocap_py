# OCAP 系统全量设计 + 全 9 域编码 + 单测全绿 执行计划

## Context（背景与目标）

用户已建立 OCAP (Out-of-Control Action Plan) 半导体制造异常处置系统的工程骨架（FastAPI + Poetry + SQLAlchemy 2.0 async + PostgreSQL + Pytest），并在 [docs/BUSINESS_POINTS.md](file:///Users/ibqo/Develop/git/github/py/ocap_py/docs/BUSINESS_POINTS.md) 中定义了 9 个业务域、60+ 业务点。

本任务要求：对标工业界最先进水平，输出完整设计文档集（概要设计、数据流图、用例图、功能设计图、数据库设计、API 字段级设计、DB 容量规划、性能要求、架构图、部署架构、macOS 12.7 单机部署方案、测试方案），并**全部 9 个业务域编码实现**，配打底数据与 mock 三方 API，**单元测试全绿**。

### 已确认的关键决策
- 实现范围：**全部 9 个业务域**
- 单测 DB：**SQLite 内存库**（ORM 模型可移植，集成测试可切 PostgreSQL）
- 认证：**JWT（用户名/密码）**
- 工作流引擎：**内嵌轻量状态机（BPMN-lite，纯 Python，无外部依赖）**
- 图表：**Mermaid**（IDE/GitHub 可渲染）
- 部署：**单机 macOS 12.7**

---

## 一、交付物总览

### A. 设计文档（docs/design/，Mermaid 图）

| # | 文件 | 内容 |
|---|---|---|
| 01 | `01_概要设计_HLD.md` | 系统定位、设计目标、9 域功能子项细化、技术架构总览 |
| 02 | `02_数据流图_DFD.md` | L0/L1/L2 数据流图（Mermaid flowchart） |
| 03 | `03_用例图.md` | 6 类角色 × 用例（Mermaid graph / PlantUML 风格） |
| 04 | `04_功能设计图.md` | 9 域功能分解图、域间交互图 |
| 05 | `05_数据库设计.md` | ER 图（Mermaid erDiagram）+ 全表 DDL + 视图 + 索引 |
| 06 | `06_API详细设计.md` | REST 端点清单 + 每端点请求/响应字段级定义 |
| 07 | `07_DB容量规划与性能要求.md` | 容量估算、性能指标、SLA |
| 08 | `08_架构与部署设计.md` | 逻辑架构图、部署架构图、macOS 12.7 单机部署方案 |
| 09 | `09_测试方案.md` | 测试策略、矩阵、单测/集成/mock/seed 方案 |

### B. 代码实现（app/，全 9 域）

按域驱动重构：`app/domains/<domain>/{models,schemas,service,api}.py` + 跨域 `core/`、`db/`、`workflow_engine/`、`integrations/`。

### C. 测试与数据

- `tests/`：全 9 域单测 + 端到端集成测试，**全绿**
- `app/db/seed/data/*.yaml`：打底数据（tenant/users/roles/rules/templates/knowledge/fake_store 等）
- `app/integrations/fake/`：mock 三方客户端（SPC/FDC/MES/AMS/SFMM/YMS/DMS/APC/Recipe）

---

## 二、模块/包布局

```
app/
  main.py                      # 扩展 lifespan 注册全部 router
  core/
    config.py                  # 扩展 JWT/DB_DRIVER/seed 配置
    security.py                # JWT 签发/校验 + passlib 密码哈希
    deps.py                    # get_db/get_current_user/require_role/require_permission
    exceptions.py              # OcapError 体系 + exception_handler
    i18n.py tenant.py logging.py pagination.py
    types.py                   # TypeDecorator: JSONBCompat/ChoiceType/Guid/BigIntVariant
  db/
    base.py                    # Base + IDMixin/TenantMixin/TimestampMixin
    session.py                 # 改造为 create_engine_from_settings 工厂（sqlite/pg 可切）
    seed/{loader.py, data/*.yaml}
  workflow_engine/             # 内嵌 BPMN-lite（types/engine/compiler/expressions/persistence/timers/visualizer）
  integrations/                # base/dtos/registry + spc/fdc/mes/ams/sfmm/yms/dms/apc/recipe + fake/store
  domains/
    common/{enums.py, mixins.py}
    trigger/      (BP-A)  models schemas service api + rules_engine dedup sources/
    workflow/     (BP-B)  models schemas service api + sop interventions
    rca/          (BP-C)  models schemas service api + cpm five_why fishbone fta graph_query
    action/       (BP-D)  models schemas service api + signatures recipe_linkage batch_disposition scripts rollback
    integration/  (BP-E)  models schemas service api + dispatcher data_quality
    knowledge/    (BP-F)  models schemas service api + graph reuse versions
    analytics/    (BP-G)  models schemas service api + kpi pareto trend g2g ram report_8d predict
    compliance/   (BP-H)  models schemas service api + audit electronic_record spc_spec retention
    platform/     (BP-I)  models schemas service api + notifications config_center plugins
  api/v1/{auth.py, health.py, __init__.py 聚合 router}
  utils/{time.py, json_utils.py, snowflake.py}
tests/
  conftest.py                  # engine/db_session/seeded_db/fake_integrations/authed_client
  unit/<domain>/...            # 每域单测
  integration/test_ocap_e2e.py # 端到端主流程
```

删除空的 `app/models/`、`app/schemas/`、`app/services/` 扁平目录（避免 `--cov` 噪音）。

---

## 三、数据库 Schema 设计要点

### 3.1 类型可移植（关键，决定 SQLite 单测能否跑通）
`core/types.py` 提供 TypeDecorator：
- `JSONBCompat`：PG→JSONB，SQLite→JSON(TEXT)
- `ChoiceType(Enum)`：存 `.name`，PG 可 variant ENUM
- `Guid`：PG→UUID，SQLite→CHAR(32)
- `BigIntVariant`：`BigInteger().with_variant(Integer, "sqlite")`

**约束**：service 层禁止使用 PG-only 操作符（`->>`、`@>`、ARRAY）；JSON 字段统一 Python 层解析；全文检索 PG 用 `to_tsvector`、SQLite 用 `LIKE` 分支。

### 3.2 核心表清单（按域，详见设计文档 05）
- 跨域：`tenants / users / roles / permissions / role_permissions / user_roles / audit_logs / electronic_records / electronic_signatures / retention_policies / notifications / config_items / metric_samples`
- BP-A：`trigger_rules / trigger_rule_versions / ocap_events / event_dedup_windows`
- BP-B：`workflow_templates / workflow_template_versions / workflow_instances / workflow_nodes / workflow_transitions / workflow_interventions / workflow_node_timeouts / sop_library`
- BP-C：`rca_records / rca_five_why / rca_fishbone / rca_fta / rca_data_correlations / case_similarity / cpm_runs`
- BP-D：`actions / action_executions / slas / action_sla / action_signatures / recipe_changes / maintenance_orders / batch_dispositions / closure_validations / action_scripts`
- BP-E：`integration_configs / sync_logs / data_quality_issues / event_streams`
- BP-F：`knowledge_cases / knowledge_case_versions / knowledge_graph_nodes / knowledge_graph_edges / solution_templates / expert_rules / knowledge_versions`
- BP-G：`kpi_snapshots / analytics_reports / pareto_caches / g2g_cycles`
- BP-H：`spc_specs / spc_spec_versions`（审计/电子记录表已在跨域）
- BP-I：`plugins`（其余已在跨域）

### 3.3 通用约定
PK 自增 BigInt；多租户列 `tenant_id`（service 层过滤模拟 RLS）；`created_at/updated_at`；软删除 `deleted_at`；可变行乐观锁 `version`；统一 `(tenant_id, created_at)` 复合索引。

---

## 四、内嵌状态机引擎（BP-B 核心）

`workflow_engine/`：纯 Python，无外部依赖。
- **抽象**：`Node(key,type,name,assignee_role,timeout_s,on_enter,on_exit,decision_tree,metadata)`、`Transition(from_,to,guard,label,priority)`、`Context(instance_id,tenant_id,event,variables,history,pending_signals)`、`NodeType{START,TASK,DECISION,FORK,JOIN,MERGE,WAIT,END}`
- **表达式求值**：`expressions.py` 用 `ast.parse(mode="eval")` 白名单（BoolOp/Compare/Name/Subscript/Constant/IfExp），禁 builtins/Call/Import，guard 失败返回 False
- **引擎**：`StateMachine.start/_activate/_evaluate_outgoing/take_decision/complete_task/join_ready/is_terminal`，支持串行/FORK并行/JOIN会签/MERGE或签/DECISION动态决策树/END终态
- **持久化**：`workflow_instances.context` 存 variables/history 摘要；`workflow_nodes` 行对应激活节点；`workflow_transitions` 追加流转；乐观锁 `version+1 WHERE id=? AND version=?` 重试 3 次
- **超时**：`timers.py` 后台 asyncio 每 30s 扫 `workflow_node_timeouts`，触发 escalation + 通知
- **不依赖任何 domain**，domain 单向调引擎

---

## 五、JWT 认证（core/security.py + api/v1/auth.py）

- 新增依赖：`pyjwt`、`passlib[bcrypt]`、`aiosqlite`、`pyyaml`
- `core/security.py`：`CryptContext(bcrypt)`、`create_access_token/refresh_token`（claims: sub/tenant_id/roles/scopes/exp/iat/jti，HS256）、`decode_token`
- `core/deps.py`：`OAuth2PasswordBearer` + `get_current_user` + `require_role(*roles)` + `require_permission(*perms)`
- `api/v1/auth.py`：`POST /auth/login`、`POST /auth/refresh`、`GET /auth/me`
- seed 预置角色：admin/engineer/supervisor/operator/auditor；权限码如 `ocap:event:create`、`ocap:workflow:advance`、`ocap:action:sign`、`ocap:audit:read`
- 单测 bcrypt 慢 → 夹具注入 sha256 替换（生产仍 bcrypt）

---

## 六、Mock 三方 API（integrations/）

- `base.py`：`IntegrationClient` ABC + `system_code` + `health()`
- `dtos.py`：`SpcChartDTO/SpcEventDTO/FdcAlarmDTO/BatchDTO/RecipeDTO/MaintenanceOrderDTO/YieldDTO/DefectDTO/AlarmDTO`
- `fake/store.py`：`FakeStore` 单例，从 `seed/data/10_fake_store.yaml` 装载，内存增删改查
- `fake/{spc,fdc,mes,ams,sfmm,yms,dms,apc,recipe}.py`：各 fake client，共享 FakeStore
- `registry.py`：`IntegrationRegistry.get(system_code, tenant_id)`，按 `integration_configs.mode` 切 mock/live
- 单测强制 mock：`app.dependency_overrides[IntegrationRegistry]`

---

## 七、测试策略（目标单测全绿）

### 7.1 conftest（tests/conftest.py，重写）
- `engine`：`sqlite+aiosqlite:///:memory:`，`PRAGMA foreign_keys=ON`，`Base.metadata.create_all`
- `db_session`：每测独立 session，结束 rollback
- `seeded_db`：`SeedLoader` 加载全部 yaml
- `fake_store` / `fake_integrations`：FakeStore + Registry
- `app_overrides`：override `get_db`、`IntegrationRegistry`
- `client` / `authed_client`：ASGITransport + 登录注入 Bearer

### 7.2 单测覆盖矩阵（每域多文件，覆盖 P0/P1 业务点，P2 stub 至少 1 测试）
- BP-A：rules_engine / dedup / sources
- BP-B：engine（串并行/FORK/JOIN/MERGE/DECISION/END）/ compiler / persistence / service
- BP-C：cpm / five_why / fishbone / fta / correlation / repeat_detection
- BP-D：signatures（hash 链）/ hold_release（+回滚）/ sla / scripts / closure
- BP-E：clients / dispatcher / data_quality
- BP-F：search / graph / versions
- BP-G：kpi / pareto / trend / g2g / ram / 8d
- BP-H：audit（不可篡改）/ electronic_record（hash 链）/ spc_spec / retention
- BP-I：i18n / multi_tenant / notifications / config_center
- 跨域：auth（JWT 颁发/校验/角色）/ health

### 7.3 测试纪律
- 每测独立 engine，无跨测污染；时间用 `time-machine` 注入；`pytest-asyncio` auto 模式；P2 stub 必有入口测试；mock 三方 100% fake，禁真实网络
- `pyproject.toml`：`--cov-fail-under` 渐进（先设可达成值，最终提至 70%+）

---

## 八、实施顺序（让单测尽早全绿，可中断恢复）

1. **依赖与基础设施**：`pyproject.toml` 追加 pyjwt/passlib/aiosqlite/pyyaml/time-machine → `core/types.py` → `db/base.py` → 改造 `db/session.py`（工厂可切 sqlite/pg）→ 删除空扁平目录
2. **认证层**：`core/security.py` + `core/deps.py` + `core/exceptions.py` + `api/v1/auth.py` + 单测
3. **seed 加载器** + `seed/data/*.yaml`（tenant/users/roles 优先，含 fake_store）
4. **workflow_engine** 独立交付 + 单测（不依赖 domain）
5. **integrations** 抽象 + fake clients + 单测
6. **主闭环 4 域**：trigger(BP-A) → workflow(BP-B) → rca(BP-C) → action(BP-D)，每域 models/schemas/service/api + 单测
7. **横向 5 域**：integration(BP-E) → knowledge(BP-F) → analytics(BP-G) → compliance(BP-H) → platform(BP-I)
8. **端到端集成测试**：1~2 条 OCAP 主流程（事件→实例→行动→闭环）
9. **设计文档**：与编码并行/收尾，9 份 docs/design/*.md（Mermaid）
10. **收尾**：alembic env.py + 初始 migration；README 更新部署/测试说明

> 实施中每完成一域即运行单测确保该域绿，再进入下一域；全 9 域完成后运行全量单测确保全绿。

---

## 九、关键文件清单

**需改造（现有）**：
- [pyproject.toml](file:///Users/ibqo/Develop/git/github/py/ocap_py/pyproject.toml) — 追加依赖、调整 cov 阈值
- [app/core/config.py](file:///Users/ibqo/Develop/git/github/py/ocap_py/app/core/config.py) — 扩展 JWT/DB_DRIVER/seed 配置
- [app/db/session.py](file:///Users/ibqo/Develop/git/github/py/ocap_py/app/db/session.py) — 改造为可切 sqlite/pg 的 engine 工厂
- [app/main.py](file:///Users/ibqo/Develop/git/github/py/ocap_py/app/main.py) — 注册全部 router
- [app/api/v1/__init__.py](file:///Users/ibqo/Develop/git/github/py/ocap_py/app/api/v1/__init__.py) — 聚合 router
- [tests/conftest.py](file:///Users/ibqo/Develop/git/github/py/ocap_py/tests/conftest.py) — 重写测试夹具

**新建（核心）**：
- `app/core/{security,deps,exceptions,i18n,tenant,types,pagination}.py`
- `app/db/base.py` + `app/db/seed/{loader.py,data/*.yaml}`
- `app/workflow_engine/{types,engine,compiler,expressions,persistence,timers,visualizer}.py`
- `app/integrations/{base,dtos,registry}.py` + `fake/{store,spc,fdc,mes,ams,sfmm,yms,dms,apc,recipe}.py`
- `app/domains/{common,trigger,workflow,rca,action,integration,knowledge,analytics,compliance,platform}/...`
- `tests/unit/<domain>/*.py` + `tests/integration/test_ocap_e2e.py`
- `docs/design/01_~09_*.md`

**权威参考**：[docs/BUSINESS_POINTS.md](file:///Users/ibqo/Develop/git/github/py/ocap_py/docs/BUSINESS_POINTS.md)（9 域 60+ 业务点编码与测试覆盖对照）

---

## 十、验证方式（end-to-end）

1. **依赖安装**：`poetry install`
2. **全量单测**：`poetry run pytest -v`（SQLite 内存库，无需外部服务）→ **必须全绿**
3. **覆盖率**：`poetry run pytest --cov=app --cov-report=term-missing` → 达到设定阈值
4. **端到端流程测试**：`poetry run pytest tests/integration -v` → 事件触发→工作流推进→根因→行动→闭环 验证通过
5. **本地启动**（macOS 12.7）：
   - `cp .env.example .env`（DB_DRIVER=sqlite 或本地 pg）
   - `poetry run uvicorn app.main:app --reload`
   - `GET /api/v1/health` 返回 ok
   - `POST /api/v1/auth/login` 登录获取 JWT
   - 用 JWT 调各域 API，验证 mock 三方联动
6. **设计文档**：9 份 docs/design/*.md 中 Mermaid 图在 IDE 预览正常渲染

---

## 十一、风险与缓解

| 风险 | 缓解 |
|---|---|
| 全 9 域一次性编码单测全绿难 | P0/P1 完整实现，P2 仅接口+stub+占位测试；按域逐个交付，每域绿后再合 |
| SQLite/PG 行为差异（JSON/枚举/外键/并发） | TypeDecorator 统一封装；service 禁用 PG-only 操作符；外键 PRAGMA conftest 开启；并发用乐观锁 |
| 状态机并发推进死锁 | 乐观锁+重试上限；JOIN 判定基于 `workflow_nodes.status` |
| bcrypt 单测慢 | 夹具注入 sha256 替换 |
| `--cov` 门槛 | 删空模块；P2 stub 至少 1 测试；阈值渐进 |
| 范围极大耗时 | 垂直切片，可中断恢复；每域自包含 |

---

## 十二、对标工业界最先进水平

- 对标 Applied Materials SmartFactory Knowledge Advisor：EI 定位、SPC/FDC 集成、引导式排查、CPM、GEP 合规、降低 50% 人为错误
- 对标 SEMI 全系列标准（E10/E30/E37/E87/E90/E94/E116/E1275）接口规范
- 对标 ISA-95 集成分层、ISO 9001/IATF 16949 8D 流程、21 CFR Part 11 电子记录/签名
- 对标 GB/T 39116 智能制造能力成熟度三级
- 工程实践：DDD 域驱动、乐观锁并发、hash 链不可篡改审计、BPMN-lite 自研引擎、可移植 ORM、全链路单测
