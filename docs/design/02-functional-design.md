# OCAP 功能设计图（Functional Design）

> 9 个业务点的功能分组、模块关系图、与外部系统的调用关系

```mermaid
mindmap
  root((OCAP 系统))
    BP-A 异常触发与事件
      SPC/FDC 报警订阅
        参数异常订阅
        规则命中拉取
      手动上报
        单条创建
        批量导入 CSV
      事件关联
        父子事件
        同机合并
      状态机
        Open / Investigating / Closed
      SLA / 升级
        一级 30min
        二级 15min
    BP-B 工作流
      模板管理
        BPMN-lite DSL
        版本发布
      实例启动
        事件驱动
        手动
      节点推进
        人工 / 自动
      干预
        回退
        跳转
        终止
      乐观锁版本号
    BP-C 根本原因 RCA
      CPM 上下文模式匹配
        特征权重
        相似度打分
      FiveWhy
      Fishbone 鱼骨图
      8D
      方法配置
    BP-D 行动计划
      创建/指派
      SLA 倒计时
      执行日志
      电子签核
        4 眼原则
        Hash 链
      批次处置
        Hold / Release / Scrap / Rework
      回滚
      闭环校验
    BP-E 集成
      SPC 统计过程控制
      FDC 设备故障检测
      MES 制造执行
      APC 先进过程控制
      YMS 良率
      DMS 缺陷
      AMS 报警
      SFMM 配方管理
      Recipe Manager
      统一 Mock 实现
    BP-F 知识
      案例库
      相似度推荐
      审核工作流
        draft / review / published / retired
      知识图谱
        实体
        关系
        路径
      版本管理
    BP-G 分析
      KPI
        MTTR / MTTD
        SLA Compliance
        Closed Rate
      Pareto
        设备 / 工序 / 产品
      G2G 批次良率
      8D 报告
      仪表盘
      报表导出
    BP-H 合规
      审计日志
        只追加
        Hash 链
      电子记录
        21 CFR Part 11
      保留策略
        保留期
        合法持有
        销毁
      合规验证
        链完整性
    BP-I 平台
      多租户
      用户 / 角色 / 权限 RBAC
      JWT 鉴权
      通知
        站内
        邮件 / Webhook
      导出
      系统配置
      审计中间件
```

---

## 1. 功能模块关系图（依赖方向）

```mermaid
graph TD
    subgraph Inputs["输入（报警/手动）"]
        SPC[SPC 报警] --> A
        FDC[FDC 报警] --> A
        MAN[手动上报] --> A
    end
    A[BP-A 事件] --> B[BP-B 工作流]
    A --> C[BP-C RCA]
    B --> D[BP-D Action]
    C --> D
    D --> E[BP-E 集成：MES]
    D --> Y[BP-E 集成：APC/Recipe]
    A --> G[BP-G 分析]
    D --> G
    C --> F[BP-F 知识]
    F --> C
    D --> H[BP-H 合规：签名/审计]
    A --> H
    G --> H
    I[BP-I 平台] --> A & B & C & D & E & F & G & H
```

## 2. 核心功能点与 API 数量矩阵

| BP | 模块 | 聚合根 | 主要 API 数量（设计值） | 已实现 API（代码中） |
| --- | --- | --- | --- | --- |
| A | Triggers/Event | Event | 10-12 | events CRUD + advance + merge + SLA 升级 |
| B | Workflow | Template + Instance | 12-14 | templates CRUD + publish + instances start/advance/rollback/jump/cancel + steps |
| C | RCA | Rca + CPM | 8-10 | CRUD + cpm/search + methods/list + approve |
| D | Action | Action + Signature + SLA | 12-14 | CRUD + execute + rollback + signatures + batch-dispositions + closure + SLAs + breaches |
| E | Integration | Client + Config | 10-12 | 各三方 GET + sync + configs CRUD + test |
| F | Knowledge | Case + Graph | 10-12 | cases CRUD + publish/reject + review + search + graph/entities/relations/paths |
| G | Analytics | KPI + Pareto + G2G + Report | 8-10 | kpis CRUD + trend + pareto + g2g + reports/8d + snapshots |
| H | Compliance | Audit + Record + Retention | 6-8 | audits list + verify + records + retention_policies CRUD + legal_holds |
| I | Platform | User/Role/Tenant/Config/Notify/Export | 16-20 | auth login + users + roles + tenants + notifications + exports + configs + health |

**合计 API：86-112**（与当前代码实现规模匹配）

## 3. 功能设计原则

1. **单职责 API**：一个 REST 资源只做一件事；复杂操作用子资源（如 `/actions/{id}/signatures`）
2. **幂等读+幂等写**：读 API 100% 幂等；写 API 通过 `Idempotency-Key` 或业务唯一键
3. **审计默认开启**：所有 POST/PUT/PATCH/DELETE 写审计，`/auth/login` 单独记录
4. **租户隔离第一**：所有业务查询必须带 `tenant_id`，唯一键 `(tenant_id, biz_code)`
5. **可回退设计**：工作流节点有 `rollback`，行动有 `rollback_action`，签名不可回退但可追加
6. **闭环校验**：事件 `closed` 要求存在已 `published` RCA + 已 `completed` action 且签名数 ≥ 1

