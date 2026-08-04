# OCAP HTTP API 设计（RESTful v1，精确到字段）

> Base URL：`/api/v1` | 所有 API 默认：
> - 鉴权：`Authorization: Bearer <JWT>`，登录除外
> - 租户：从 JWT `tid` claim 取（`/auth/*` 登录除外）
> - 幂等头：写 API 可带 `Idempotency-Key: <uuid>`，重复请求返回首次响应
> - 请求 ID：响应头 `X-Request-ID`
> - 响应通用结构：成功直接返回资源模型；失败：`{"code":"<ERR>","message":"...","details":{...}}`
> - 分页：`?page=1&page_size=20`，列表响应 `{ "items": [...], "total": N, "page": n, "page_size": s }`

---

## 1. 鉴权与平台（BP-I）

### POST /auth/login
登录取 JWT。
```json
// 请求
{ "username": "eng1", "password": "xxx", "tenant_code": "fab_a" }
// 响应 200
{ "access_token": "<JWT>", "token_type": "Bearer", "expires_in": 3600,
  "user": { "id": 1, "username": "eng1", "roles": ["engineer"], "tenant_id": 1 } }
```

### GET /users?page=&page_size=&role_code=&q=
返回用户列表。

### POST /users
创建用户（admin）：
```json
{ "username": "eng2", "email": "eng2@fab.com", "password": "S3cret!",
  "full_name": "工程师 2", "role_ids": [2,3] }
```

### GET /users/{user_id} / PATCH /users/{user_id} / DELETE /users/{user_id}

### GET /roles / POST /roles / GET /roles/{id} / PATCH /roles/{id}
```json
// POST /roles
{ "code": "shift_leader", "name": "值班长", "permission_codes": [
   "ocap:event:create","ocap:event:view","ocap:action:execute",
   "ocap:action:sign","ocap:workflow:advance" ] }
```

### GET /tenants / POST /tenants（super_admin）
```json
{ "code": "fab_b", "name": "Fab B", "settings": {"timezone":"Asia/Shanghai"} }
```

### GET /configs / POST /configs（admin：scope=tenant；super_admin：可 scope=global）
```json
// POST
{ "key": "rca.cpm.top_n", "value": 5 }
// GET /configs?key=rca.cpm.top_n → [{"id":1,"key":"rca.cpm.top_n","value":5}]
```

### GET /notifications / POST /notifications/{id}/read
```json
// 列表响应
{ "items":[{"id":1,"type":"sla","title":"SLA 升级","body":"...","read_at":null,"url":"/events/1"}],"total":1,"page":1,"page_size":20}
```

### POST /exports / GET /exports / GET /exports/{id}/download
```json
// POST
{ "resource": "events", "format": "xlsx", "filters": {"status":"open","equipment_id":"EQP-01"} }
// 响应：{ "id": 1, "status": "completed", "download_url": "/api/v1/exports/1/download" }
```

### GET /healthz、GET /readyz、GET /metrics（可选 Prometheus）

---

## 2. BP-A 异常触发与事件

### POST /triggers/rules
```json
{ "code": "SPCTYPE1", "name": "Type1 西电规则", "source": "spc",
  "condition": {"rule":"we_rule_1","param":"ETCH01.THICK"},
  "priority": 100, "debounce_window_s": 60,
  "dedup_key_tpl": "{{equipment_id}}|{{param_code}}",
  "enabled": true, "workflow_template_code": "OCAP-THICK-DEF" }
```

### GET /triggers/rules、GET /triggers/rules/{id}、PATCH /triggers/rules/{id}、POST /triggers/rules/{id}/publish、POST /triggers/rules/{id}/enable、POST /triggers/rules/{id}/disable

### POST /triggers/events（手动 / 报警入口）
```json
// 手动
{ "source": "manual", "severity": "warning",
  "equipment_id": "EQP-01", "process_step": "ETCH-03",
  "technology_node": "5nm", "production_line": "FAB-A",
  "batch_id": "LOT-2026-0803-001", "product_id": "PRD-A1",
  "title": "Thickness 严重偏移",
  "parameters": {"measured":7.8,"target":6.0,"delta_sigma":3.2} }
// 响应 201 { "id": 1, "status": "open", "dedup_key": "...", ... }
```

### GET /triggers/events?status=&equipment_id=&severity=&detected_from=&detected_to=&page=&page_size=
响应分页。

### GET /triggers/events/{id}
```json
{ "id":1, "tenant_id":1, "source":"manual", "severity":"warning",
  "detected_at":"2026-07-30T08:00:00Z", "equipment_id":"EQP-01",
  "process_step":"ETCH-03", "parameters":{"measured":7.8,"target":6.0,"delta_sigma":3.2},
  "trigger_rule_id":null, "status":"open", "merged_into_id":null,
  "title":"Thickness 严重偏移", "created_at":"...","updated_at":"..." }
```

### POST /triggers/events/{id}/advance（事件状态推进）
```json
{ "status": "investigating" | "closed" }
// closed 需要通过 v_closure_readiness = true，否则 409
```

### POST /triggers/events/merge
```json
{ "ids": [1,2,3], "keep_id": 1, "reason": "同批次同类异常" }
```

### GET /triggers/events/{id}/related
返回合并/关联事件树。

### GET /triggers/sla/breaches?scope=all&window_days=7
返回正在超时的事件。

---

## 3. BP-B 工作流

### POST /workflows/templates
```json
{ "code": "OCAP-THICK-DEF", "name": "厚度偏差 OCAP 模板",
  "definition": {
    "nodes": [
      {"key":"n1","type":"startEvent","name":"开始"},
      {"key":"n2","type":"userTask","name":"RCA 分析","assignee":"engineer"},
      {"key":"n3","type":"userTask","name":"Action 指派","assignee":"engineer"},
      {"key":"n4","type":"endEvent","name":"结束"}
    ],
    "edges": [{"from":"n1","to":"n2"},{"from":"n2","to":"n3"},{"from":"n3","to":"n4"}]
  } }
```

### GET /workflows/templates / GET /workflows/templates/{id} / PATCH /workflows/templates/{id}

### POST /workflows/templates/{id}/publish / POST /workflows/templates/{id}/retire

### POST /workflows/instances
```json
{ "template_code": "OCAP-THICK-DEF", "event_id": 1, "start_context": {"tech":"5nm"} }
// 响应 201
{ "id":1, "template_id":1, "event_id":1, "status":"running",
  "current_node_key":"n2", "context":{...}, "version":0 }
```

### GET /workflows/instances / GET /workflows/instances/{id} / GET /workflows/instances/{id}/steps

### POST /workflows/instances/{id}/advance
```json
{ "action": "complete_task", "node_key": "n2",
  "output": {"rca_id": 42, "recommended_case_ids":[11,12]} }
// 或 intervention
{ "action": "rollback", "node_key": "n3", "target_key": "n2", "reason": "RCA 需修正" }
// 或 jump / cancel / terminate
```
注意：冲突用 409 + 携带 `current_version` 做乐观重试。

### GET /workflows/sop/library / POST /workflows/sop/library（admin）
SOP 条目 CRUD。

---

## 4. BP-C 根本原因分析 RCA

### POST /rcas
```json
{ "event_id": 1, "method": "five_why",
  "evidence": {
    "why1":"厚度偏大","why2":"刻蚀速率偏低","why3":"RF 功率下降",
    "why4":"RF 匹配器老化","why5":"未按 PM 周期保养" },
  "root_cause": "匹配器 PM 周期过长导致老化，RF 功率低于规格",
  "conclusion": "更换 RF 匹配器，并将 PM 周期从 30d 调整为 14d" }
// method ∈ { five_why, fishbone, eight_d, fta, cpm }
```

### GET /rcas / GET /rcas/{id} / PATCH /rcas/{id}

### POST /rcas/{id}/approve / POST /rcas/{id}/reject
```json
// approve
{ "review_note": "root cause 逻辑清晰，同意发布" }
```

### POST /rcas/cpm（上下文模式匹配，快速推荐）
```json
{ "event_id": 1,
  "context": {"equipment_id":"EQP-01","process_step":"ETCH-03",
              "technology_node":"5nm","anomaly_type":"Thickness"},
  "top_n": 5 }
// 响应 200
{ "top_score": 88, "recommendations": [
    {"case_id": 1, "score": 88, "matched_features": ["equipment_id","process_step","technology_node","anomaly_type"],
     "title": "历史：Thickness 偏移", "root_cause":"...", "solution":"..."}
  ] }
```

### GET /rcas/methods
返回支持的方法及元数据。

### POST /rcas/repeat-detections
```json
{ "event_id": 1, "window_days": 30 }
→ { "repeated": true, "count": 3, "matched_events":[...] }
```

---

## 5. BP-D 行动计划与电子签名

### POST /actions
```json
{ "event_id": 1, "type": "maintenance",
  "title": "更换 RF 匹配器并保养",
  "description": "PM 周期从 30d 调为 14d",
  "assignee_id": 7, "target_equipment_id": "EQP-01", "due_in_minutes": 240 }
// type ∈ { maintenance, recipe_change, disposition, param_tune, hold, pm_order, other }
```

### GET /actions / GET /actions/{id} / PATCH /actions/{id} / DELETE /actions/{id}

### POST /actions/{id}/execute
```json
{ "detail": "已更换，RF 功率恢复规格", "params": {"before_watts":780,"after_watts":1000} }
→ 200 { "id":1, "action_id":1, "executor_id":7, "detail":"...", "result_data":{...}, "executed_at":"..." }
```

### POST /actions/{id}/rollback
```json
{ "reason": "执行参数错误，需重新执行" }
```

### POST /actions/{id}/signatures（电子签核，Hash 链 append）
```json
{ "meaning": "Approve", "comment": "同意，已复核行动执行结果" }
// meaning ∈ { Approve, Reject, Acknowledge, Witness }
// 响应 201
{ "id":5, "action_id":1, "signer_id":3, "meaning":"Approve",
  "sequence":2, "prev_hash":"<hex64>", "record_hash":"<hex64>", "signed_at":"..." }
```

### GET /actions/{id}/signatures
返回顺序数组（sequence 升序）。

### POST /actions/slas
```json
{ "bound_type": "action", "bound_id": 1, "name": "首响应 SLA",
  "stage": "first_response", "duration_minutes": 30 }
```
### GET /actions/slas / GET /actions/slas/breaches

### POST /actions/{id}/batch-dispositions（MES 集成调用）
```json
{ "batch_id": "B2026-001", "disposition": "hold", "reason": "Thickness 异常待复检" }
// disposition ∈ { hold, release, scrap, rework }
// 响应 201
{ "id":1, "action_id":1, "batch_id":"B2026-001", "disposition":"hold",
  "requested_at":"...", "external_result":{"success":true,"new_status":"held"} }
```

### POST /actions/{id}/closure（闭环校验）
```json
// 空 body
// 响应 201
{ "action_id":1, "ready":true, "checks": [
   {"name":"has_execution","passed":true},
   {"name":"has_signature","passed":true},
   {"name":"batch_disposition_ok","passed":true}
 ] }
```

---

## 6. BP-E 集成

### GET /integrations/configs / POST /integrations/configs / GET /integrations/configs/{id} / PATCH /integrations/configs/{id}
```json
// POST
{ "system_code": "mes", "name": "Fab MES",
  "base_url": "https://mes.fab-a.internal/v1",
  "auth_mode": "apikey", // none/basic/apikey/oauth2/client_cert
  "credentials": {"api_key":"<ENC AES-GCM>"},
  "enabled": true }
```
注意：`credentials` 读写均以 `application/vnd.enc.v1+json` 密文展示，不回传明文。

### POST /integrations/configs/{id}/test
返回连通性 `{ "ok": true, "latency_ms": 45, "hint": null }`。

### GET /integrations/{system_code}/batches?status=running&equipment_id=...
拉取三方数据（真实或 mock，取决于 config）。

### GET /integrations/spc/alarms?from=ISO-TS&to=ISO-TS
### GET /integrations/fdc/alarms?from=ISO-TS&to=ISO-TS
### GET /integrations/mes/batches/{batch_id}
### POST /integrations/mes/batches/{batch_id}/dispose
```json
{ "disposition": "hold", "reason": "OCAP" }
```
### GET /integrations/yms/yields?batch_id=...
### GET /integrations/dms/defects?batch_id=...
### GET /integrations/apc/traces?equipment_id=...
### GET /integrations/sfmm/recipes?equipment_id=...&product=...
### GET /integrations/ams/alarms?from=...&severity=...
### POST /integrations/syncs（手动触发同步）
```json
{ "system_code": "spc", "resource": "alarms", "from": "...", "to": "..." }
```
### GET /integrations/syncs/logs?config_id=&from=&to=
### GET /integrations/dqi/issues?status=open

---

## 7. BP-F 知识管理

### POST /knowledge/cases
```json
{ "code": "KC-THICK-0001",
  "title": "ETCH-03 Thickness 偏移案例",
  "context": {"equipment_id":"EQP-01","process_step":"ETCH-03",
              "technology_node":"5nm","anomaly_type":"Thickness"},
  "equipment_id": "EQP-01",
  "root_cause": "匹配器 PM 周期过长导致老化，RF 功率低于规格",
  "solution": "更换 RF 匹配器，并将 PM 周期从 30d 调整为 14d",
  "tags": ["thickness","etch","pm","rf_matcher"] }
```

### GET /knowledge/cases / GET /knowledge/cases/{id} / PATCH /knowledge/cases/{id}

### POST /knowledge/cases/{id}/review
```json
{ "verdict": "request_changes", "note": "需要补充 PM 日志截图" }
```

### POST /knowledge/cases/{id}/publish / POST /knowledge/cases/{id}/retire

### GET /knowledge/cases/search?q=thickness&equipment_id=EQP-01
CPM 推荐之外的全文/结构化检索。

### POST /knowledge/graph/nodes、GET /knowledge/graph/nodes、PATCH /knowledge/graph/nodes/{code}
```json
{ "code": "EQP-01", "type": "equipment", "name": "刻蚀机 01",
  "props": {"model":"CCP-300X","vendor":"Tokyo Electron"} }
```

### POST /knowledge/graph/edges、GET /knowledge/graph/edges
```json
{ "from_node_code": "EQP-01", "to_node_code": "ETCH-03",
  "rel_type": "runs_process", "weight": 1.0, "props": {} }
```

### GET /knowledge/graph/paths?from=EQP-01&to=THICK&max_depth=4
```json
{ "paths": [
   [{"code":"EQP-01","type":"equipment"}, {"code":"ETCH-03","type":"process"},
    {"code":"THICK","type":"metric"}] ] }
```

### POST /knowledge/solution-templates / GET /knowledge/solution-templates / POST /knowledge/expert-rules / GET /knowledge/expert-rules

---

## 8. BP-G 分析与报告

### POST /analytics/kpis（写入 KPI 快照，写 API 由 ETL 或作业调用）
```json
{ "kpi_code": "mttr", "period": "daily",
  "snapshot_at": "2026-07-30T00:00:00Z",
  "value": 45.0, "target": 120.0, "count": 3,
  "group_by": "equipment_id:EQP-01" }
// kpi_code ∈ { mttr, mttd, mtbf, sla_compliance, close_rate,
//              rca_hit_rate, repeat_rate, action_backlog }
```

### GET /analytics/kpis?kpi_code=&from=&to=&period=
### GET /analytics/kpis/trend?kpi_code=mttr&days=30
```json
{ "points": [{"t":"...","v":45.0,"target":120.0}], "p95": 65.2, "avg": 42.1 }
```

### GET /analytics/pareto?dimension=equipment_id&days=7
```json
{ "items": [
   {"key":"EQP-01","value":12,"pct":35.3,"cum_pct":35.3},
   {"key":"EQP-02","value":8, "pct":23.5,"cum_pct":58.8}
 ] }
// dimension ∈ { equipment_id, process_step, product_id, anomaly_type, shift }
```

### GET /analytics/g2g?from=&to=&batch_id=
```json
{ "avg_turnover_sec": 48210, "target_sec": 86400, "cycles": [...] }
```

### GET /analytics/reports/8d/{event_id}
```json
{ "event_id":1,
  "d1_team":["eng1","eng2"], "d2_problem":"Thickness 严重偏移",
  "d3_interim":"Hold B2026-001",
  "d4_root_cause":"匹配器 PM 周期过长",
  "d5_corrective":"缩短 PM 周期",
  "d6_implement":"更换 RF 匹配器，PM 30d → 14d",
  "d7_preventive":"更新 PM master",
  "d8_recognize":"感谢团队",
  "generated_at":"..." }
```

### POST /analytics/reports / GET /analytics/reports

---

## 9. BP-H 合规与审计

### GET /compliance/audits?user_id=&action=&resource_type=&from=&to=&page=&page_size=
```json
{ "items": [
   {"id":1001,"user_id":3,"action":"UPDATE","resource_type":"actions","resource_id":1,
    "path":"/api/v1/actions/1", "ip_address":"10.0.0.23","request_id":"rid-abc",
    "before":{"status":"in_progress"},"after":{"status":"completed"},
    "prev_hash":"abc...","record_hash":"def...","created_at":"..."}
 ], "total": 1, "page": 1, "page_size": 20 }
```

### GET /compliance/audits/verify?limit=500
```json
{ "intact": true, "checked": 500, "broken_at": null, "first_seq": 10001, "last_seq": 10500 }
// 失败：{ "intact":false, "checked":234, "broken_at":10234, "first_seq":..., "last_seq":... }
```

### GET /compliance/records?resource_type=&resource_id=&from=&to=
电子记录列表；支持 `&download=true` 直接返回 PDF/签名包。

### POST /compliance/retention-policies / GET /compliance/retention-policies / PATCH ...
```json
{ "scope": "audit_logs:*", "retain_years": 10, "legal_hold": false }
```

### POST /compliance/legal-holds / GET ...
```json
{ "ids": [1,2,3], "resource_type": "rca_records", "reason": "客户投诉取证", "until_at": "2027-01-01" }
```

---

## 10. 常见 HTTP 错误码与业务 `code`

| HTTP | code | 典型场景 |
| --- | --- | --- |
| 400 | VALIDATION_ERROR | 请求字段校验（`details` 为 pydantic err） |
| 401 | UNAUTHENTICATED | JWT 缺失/过期/篡改 |
| 403 | FORBIDDEN | 无权限 |
| 404 | NOT_FOUND | 资源不存在 |
| 409 | CONFLICT | 乐观锁冲突 / 4眼重复签名 / 签名链断裂 / 工作流非 running / 事件闭环校验失败 |
| 410 | GONE | 资源已废弃 |
| 422 | IDEMPOTENCY_MISMATCH | 幂等键命中但请求体不同 |
| 500 | INTERNAL_ERROR / SIGNATURE_CHAIN_BROKEN | 内部错误 |
| 503 | INTEGRATION_UNHEALTHY | 三方系统连通性失败 |

---

## 11. 版本策略

- URL 版本：`/api/v1/...`
- 破坏性升级：`/api/v2/...`；`v1` 至少保留 18 个月
- 非破坏性（加字段、加可选参数、加新资源）直接追加
