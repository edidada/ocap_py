# OCAP 用例图（Use Case Diagram）

> 角色划分 + 典型用例 + 用例-功能点映射

```mermaid
usecaseDiagram
    actor Operator as "产线操作员"
    actor Engineer as "工艺工程师"
    actor Supervisor as "主管 (4眼签)"
    actor QA as "QA 工程师"
    actor Admin as "系统管理员"
    actor External as "外部系统<br/>(SPC/FDC/MES)"

    package BP-A 异常触发与事件 {
        usecase UC_A1 as "手动上报异常事件"
        usecase UC_A2 as "订阅 SPC/FDC 报警自动创建"
        usecase UC_A3 as "查看事件列表/详情/关联"
        usecase UC_A4 as "事件合并 / 拆分"
        usecase UC_A5 as "事件状态推进（闭环）"
    }

    package BP-B 工作流编排 {
        usecase UC_B1 as "维护 OCAP 模板（BPMN-lite）"
        usecase UC_B2 as "基于模板启动流程实例"
        usecase UC_B3 as "人工推进当前节点"
        usecase UC_B4 as "流程干预：回退/跳转/终止"
    }

    package BP-C 根本原因分析 {
        usecase UC_C1 as "上下文模式匹配(CPM)推荐案例"
        usecase UC_C2 as "5 Why 分析"
        usecase UC_C3 as "鱼骨图构造"
        usecase UC_C4 as "8D 结构化分析"
        usecase UC_C5 as "审核并发布 RCA 结论"
    }

    package BP-D 行动计划 {
        usecase UC_D1 as "创建/指派行动计划"
        usecase UC_D2 as "执行行动并记录"
        usecase UC_D3 as "批次处置(Hold/Release/Scrap/Rework)"
        usecase UC_D4 as "电子签名(4眼签)"
        usecase UC_D5 as "行动回滚 / 重新打开"
        usecase UC_D6 as "查看 SLA / 升级"
    }

    package BP-E 集成 {
        usecase UC_E1 as "拉取 SPC 规则命中"
        usecase UC_E2 as "拉取 FDC 报警"
        usecase UC_E3 as "MES 批次状态 / 处置"
        usecase UC_E4 as "APC / Recipe 下发 / 比对"
        usecase UC_E5 as "YMS 良率 / DMS 缺陷 拉取"
    }

    package BP-F 知识 {
        usecase UC_F1 as "新建知识案例草稿"
        usecase UC_F2 as "审核案例并发布/退回"
        usecase UC_F3 as "案例检索 / 相似度推荐"
        usecase UC_F4 as "维护知识图谱实体/关系"
        usecase UC_F5 as "图谱路径推理"
    }

    package BP-G 分析与报告 {
        usecase UC_G1 as "KPI 看板 (MTTR/MTTD/SLA)"
        usecase UC_G2 as "Pareto 分析 (设备/工序/产品)"
        usecase UC_G3 as "G2G 良率趋势"
        usecase UC_G4 as "8D 报告导出"
    }

    package BP-H 合规 {
        usecase UC_H1 as "审计日志查询"
        usecase UC_H2 as "审计链完整性校验"
        usecase UC_H3 as "电子记录搜索/导出"
        usecase UC_H4 as "保留策略 / 合法持有"
    }

    package BP-I 平台 {
        usecase UC_I1 as "租户 / 用户 / 角色 / 权限"
        usecase UC_I2 as "登录 / JWT 鉴权"
        usecase UC_I3 as "站内通知 / Webhook"
        usecase UC_I4 as "报表导出"
        usecase UC_I5 as "系统配置"
    }

    Operator --> UC_A1
    Operator --> UC_A3
    Operator --> UC_D2
    Operator --> UC_D3

    Engineer --> UC_A1
    Engineer --> UC_A3
    Engineer --> UC_A5
    Engineer --> UC_B2
    Engineer --> UC_B3
    Engineer --> UC_C1
    Engineer --> UC_C2
    Engineer --> UC_C3
    Engineer --> UC_C4
    Engineer --> UC_D1
    Engineer --> UC_D2
    Engineer --> UC_D3
    Engineer --> UC_D5
    Engineer --> UC_F1
    Engineer --> UC_F3
    Engineer --> UC_F4
    Engineer --> UC_G1
    Engineer --> UC_G2
    Engineer --> UC_G3
    Engineer --> UC_H1

    Supervisor --> UC_A3
    Supervisor --> UC_A5
    Supervisor --> UC_B4
    Supervisor --> UC_C5
    Supervisor --> UC_D4
    Supervisor --> UC_F2
    Supervisor --> UC_G4
    Supervisor --> UC_D6

    QA --> UC_A3
    QA --> UC_C5
    QA --> UC_D4
    QA --> UC_F2
    QA --> UC_H2
    QA --> UC_H3
    QA --> UC_H4

    Admin --> UC_I1
    Admin --> UC_I2
    Admin --> UC_I3
    Admin --> UC_I4
    Admin --> UC_I5
    Admin --> UC_B1
    Admin --> UC_H4

    External --> UC_A2
    External --> UC_E1
    External --> UC_E2
    External --> UC_E3
    External --> UC_E4
    External --> UC_E5
```

---

## 1. 用例与业务点矩阵

| 用例 ID | 主要角色 | 前置条件 | 后置条件 | 对应 BP |
| --- | --- | --- | --- | --- |
| UC_A1 | Operator/Engineer | 登录 + 权限 `ocap:event:create` | Event 状态 = open，审计写入 | BP-A |
| UC_A2 | External | 集成配置可用 | Event 批量入库 + 触发对应工作流 | BP-A + BP-B |
| UC_A3 | Operator/Engineer | 登录 | 列表可分页/筛选 | BP-A |
| UC_A4 | Supervisor | 两个事件同源 | 事件合并 + 关系记录 | BP-A |
| UC_A5 | Engineer/Sup | 有 RCA/Action 已完成 | Event = closed，校验通过 | BP-A |
| UC_B1 | Admin | 模板草稿 | 模板版本 +1，published | BP-B |
| UC_B2 | Engineer | 模板 published | Instance = running，Start 节点激活 | BP-B |
| UC_B3 | Engineer | 当前节点是 userTask | 节点进入下一节点 | BP-B |
| UC_B4 | Supervisor | 有干预权限 | 节点状态改变 + 审计 | BP-B |
| UC_C1 | Engineer | ≥1 已发布案例 | Top-N 案例 + 分数 | BP-C |
| UC_C2 | Engineer | 存在 Event | RCA 入库 evidence.why1-5 | BP-C |
| UC_C3 | Engineer | 存在 Event | Fishbone 结构化数据 | BP-C |
| UC_C4 | Engineer | 存在 Event | 8D 字段完整 | BP-C |
| UC_C5 | Supervisor | RCA草稿完整 | RCA.status = published | BP-C |
| UC_D1 | Engineer | 事件存在 | Action = pending，SLA 计算 due_at | BP-D |
| UC_D2 | Operator/Eng | Action status 允许 | 执行记录入库 | BP-D |
| UC_D3 | Operator/Eng | MES 批次存在 | 批次状态改变 + 审计 | BP-D + BP-E |
| UC_D4 | Supervisor + QA | 至少 2 不同人 | 签名 Hash 链 append | BP-D + BP-H |
| UC_D5 | Supervisor | 无发布签名 | Action 回到 pending | BP-D |
| UC_D6 | Supervisor | SLA 配置 | 升级事件+通知 | BP-D |
| UC_E1-5 | External/Admin | 集成端点通过健康检查 | 数据同步（mock 或真实） | BP-E |
| UC_F1 | Engineer | 登录 | 草稿 = draft | BP-F |
| UC_F2 | Supervisor/QA | 草稿完整 | Case = published / rejected | BP-F |
| UC_F3 | Engineer | 已发布案例存在 | Top-N | BP-F |
| UC_F4 | Engineer | 图谱权限 | 实体/关系写入 | BP-F |
| UC_F5 | Engineer | 图谱实体存在 | 返回路径列表 | BP-F |
| UC_G1-4 | Engineer/Sup | 事件/行动数据 | 返回聚合或文件 | BP-G |
| UC_H1 | Engineer/QA | 登录 | 分页日志 | BP-H |
| UC_H2 | QA/Admin | 审计 ≥1 条 | intact=true/false + 断点 | BP-H |
| UC_H3 | QA | 登录 | 电子记录列表/下载 | BP-H |
| UC_H4 | QA/Admin | 登录 | 保留策略/合法持有 入库 | BP-H |
| UC_I1-5 | Admin | 超管权限 | 平台配置生效 | BP-I |

## 2. 关键 4 眼签核用例（UC_D4）详述

```
参与者: 工程师 E(已签1) + 主管 S(已签2) + QA Q(抽检)
前置: Action.status = executed
主成功场景:
1. E POST /actions/{id}/signatures  meaning=Approve → sig1
2. S POST /actions/{id}/signatures  meaning=Approve → sig2
   （同一 user_id 双签拒绝；sig2.prev_hash = sig1.record_hash）
3. Action.status → approved
4. 审计链 append 两条 audit_log，携带 hash 链
异常:
- 签名重复人 → 409 CONFLICT
- 哈希链断 → 500，拒绝写入
- 超过签名期限 → 409
```
