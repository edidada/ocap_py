# OCAP DB 容量规划（Capacity Planning）

> 规划周期：5 年；租户：10 租户（Fab A/B/C …）；单租户峰值规模对标 12 寸先进逻辑 Fab（月产能 30K wafers）。
> 所有容量计算均以 **单租户 1 年 / 3 年 / 5 年** 维度给出，再乘租户数得总集群。

---

## 1. 写入与行数估算（单租户 × 5 年）

| 表 | 每日写入量 | 年增长（万行） | 5 年（亿行） | 行均大小（估） | 5 年裸数据 |
| --- | --- | --- | --- | --- | --- |
| ocap_events | 1,000 | 36.5 | 1.83 | 400 B | 7.3 GB |
| trigger_rules + versions | 20 / 20 | 1.5 | 0.08 | 1 KB + 2 KB | 0.2 GB |
| workflow_instances | 800 | 29.2 | 1.46 | 1.2 KB | 17.5 GB |
| workflow_nodes | 4,000 | 146 | 7.30 | 0.5 KB | 36.5 GB |
| workflow_transitions | 4,000 | 146 | 7.30 | 200 B | 14.6 GB |
| rca_records + sub 表 | 800 × 2.5 = 2,000 | 73 | 3.65 | 0.8 KB (mean) | 29.2 GB |
| cpm_runs | 2,000 | 73 | 3.65 | 2 KB | 73 GB |
| actions | 2,500 | 91.25 | 4.56 | 0.6 KB | 27.4 GB |
| action_executions | 2,500 × 3 = 7,500 | 273.75 | 13.69 | 0.4 KB | 54.8 GB |
| action_signatures | 2,500 × 1.5 = 3,750 | 136.88 | 6.84 | 0.3 KB | 20.5 GB |
| batch_dispositions | 1,500 | 54.75 | 2.74 | 0.3 KB | 8.2 GB |
| recipe_changes + pm_orders | 500 | 18.25 | 0.91 | 0.8 KB | 7.3 GB |
| closure_validations | 2,500 × 4 = 10,000 | 365 | 18.25 | 150 B | 27.4 GB |
| knowledge_cases + versions | 20 | 0.73 | 0.04 | 2 KB | 0.08 GB |
| knowledge_graph_nodes + edges | 50 + 150/day | 7.3 | 0.37 | 0.4 KB/0.3 KB | 0.15 GB |
| kpi_snapshots（按 50 KPI × 30 组 × 日） | 1,500 | 54.75 | 2.74 | 150 B | 4.1 GB |
| pareto_caches / g2g_cycles | 100 + 500 | 21.9 | 1.10 | 1 KB / 200 B | 1.3 GB |
| metric_samples（SPC 高频） | 500,000 / 每设备 1 param / min（200 eqp × 40 param）= **24 × 60 × 200 × 40 ≈ 11,520,000/day** | 42,048 | 210.24 | 80 B | **1,682 GB / 1.6 TB** |
| audit_logs（所有写 + 部分读） | 10 × (events + actions + rca + ...) ≈ **30,000/day** | 1,095 | 54.75 | 700 B | **383 GB** |
| electronic_records + signatures | 3,000 + 2,000 = 5,000 | 182.5 | 9.13 | 1 KB mean | 91.3 GB |
| notifications | 10,000 | 365 | 18.25 | 300 B | 54.8 GB |
| sync_logs + dqi + event_streams | 2,000 + 100 + 2,000 | 149.65 | 7.48 | 0.5 KB | 37 GB |
| integration_configs + tenants + users + roles | < 5,000 总 | — | — | 1 KB | < 0.01 GB |

### 裸数据合计（单租户 × 5 年）

| 类别 | 5 年裸容量（GB） | 占比 |
| --- | --- | --- |
| 原始采样（metric_samples） | **1,682** | 56.3% |
| 审计链（audit_logs + 电子记录） | **474** | 15.9% |
| 工作流运行时 + RCA + CPM | **256** | 8.6% |
| Action + 签名 + 处置 | **146** | 4.9% |
| 分析报告 + KPI 快照 | **9** | 0.3% |
| 其它（知识/通知/集成/配置/IAM） | **182** | 6.1% |
| **单租户 5 年合计** | **~2,750 GB（2.7 TB）** | 100% |

### 因子修正

| 因子 | 倍数 | 说明 |
| --- | --- | --- |
| 索引 | × 1.6 | 组合 B-tree / BRIN / GIN 索引 |
| PostgreSQL 页头、TOAST、碎片 | × 1.4 | 默认 fillfactor 90 |
| WAL（保留 7 日 + 归档） | × 0.3 | 单租户 ≈ 800 GB |
| 预留（未来业务增长 50% headroom） | × 1.5 | |
| **合计修正因子** | × (1.6 × 1.4 × 1.5 ≈ 3.36) + 0.3 WAL | |

→ **单租户实际 SSD 需求 ≈ 2.7 TB × 3.36 + 0.8 TB ≈ 9.07 TB ≈ 10 TB SSD**
→ **10 租户总集群存储 ≈ 10 × 10 TB = 100 TB SSD**

---

## 2. 分区与归档策略（寿命管理）

| 数据集 | 在线 SSD | 近线 HDD / 对象存储 | 永久归档（合规） |
| --- | --- | --- | --- |
| metric_samples | 90 天（1.6 TB × 90/1825 ≈ 80 GB） | 10 年（按日分区迁移） | — |
| audit_logs | 12 月（~76 GB） | 10 年 | 永久（21CFR Part11） |
| electronic_records + signatures | 24 月 | 10 年 | 永久 |
| kpi_snapshots（daily） | 3 年 | 7 年 | — |
| kpi_snapshots（monthly） | 全部在线 | — | 7 年 |
| ocap_events / workflow / rca / actions 核心 | 5 年 | 10 年 | 7 年 |
| knowledge_cases | 全部在线（GB 级） | — | 永久 |
| pareto_caches / notifications | 6 月 | — | — |

### 归档工具链建议（PostgreSQL 生态）

- `pg_dump --table=audit_logs_2026_01` → S3 兼容对象存储（MinIO 本地或云）
- `pg_partman` 管理 RANGE 分区
- 冷查询：`cstore_fdw` 或外部表读取 Parquet on S3

---

## 3. 数据库服务器规格建议（PostgreSQL 单机 / macOS 12.7）

> macOS 单机是开发 / 验证环境目标（见部署文档），以下是 macOS 单物理机容量建议。
> 生产建议：Linux x86_64 / ARM64，一主两从 + pgBackRest。

### 3.1 macOS 12.7 单机（开发验证 + 单租户基线）

| 资源 | 最低 | 推荐 | 说明 |
| --- | --- | --- | --- |
| CPU | Apple M1 Pro 10C | M2 Max 12C / Intel i9-12900 | 异步 I/O + JIT |
| 内存 | 32 GB | 64 GB | shared_buffers 16 GB，work_mem 64 MB，maintenance_work_mem 2 GB |
| 系统盘（APFS） | 512 GB SSD | 1 TB NVMe SSD | 系统 + 应用 + 代码 |
| 数据盘 SSD | 2 TB NVMe SSD | **4 TB NVMe SSD** | `pgdata` / 归档 WAL |
| 网络 | 1 Gbps | 10 Gbps | 备份 / 对象存储上传 |
| macOS 版本 | 12.7 Monterey | 12.7 Monterey 最新补丁 | |
| PostgreSQL | 15.x / Homebrew | 15.x | 不要 16（少用 bleeding） |
| 备份容量 | 4 TB 外挂 USB-C | 8 TB 外挂 + S3 兼容（MinIO/Backblaze） | 3-2-1 备份原则 |

### 3.2 生产（参考：Linux + 10 租户）

- 主库：2 × Intel Xeon Gold 6430 / 256 GB RAM / 4 × 3.84 TB NVMe RAID10（有效 7.6 TB）× 2 主从对
- 从库 2 台：只读副本（报表查询 / 集成读）
- WAL 归档到对象存储（S3/MinIO）
- 连接池：PgBouncer（session pool 1000）
- 扩展：pg_stat_statements / pgstattuple / pg_buffercache / auto_explain / pg_prewarm

---

## 4. 备份、RPO、RTO

| 指标 | 目标 | 实现 |
| --- | --- | --- |
| RPO（数据丢失容忍） | ≤ 15 min | WAL 归档每 15 min 一次 + 异步复制（<1 s 常见） |
| RTO（恢复时间） | ≤ 30 min | pgBackRest 全量每周 + 差异每日，WAL PITR |
| 备份策略 | 3-2-1 原则 | 本地磁盘 → 外挂 HDD → 对象存储异地 |
| 备份保留 | 在线 14 天 + 对象存储 7 年（合规链永久） | |

---

## 5. 关键 IOPS / 吞吐估算

> 以单租户峰值（×10 为总集群）

| 场景 | 单租户 TPS（估） | 单租户 IOPS（读+写） | 存储吞吐 |
| --- | --- | --- | --- |
| 正常白天 | 200 写 + 400 读 = 600 | 写 1200 + 读 3200 = 4400 | 24 MB/s 写 |
| 峰值批上报（每 5 分钟） | 1500 | 8000 | 80 MB/s 写 |
| metric_samples 仅写入 | 持续 ~135/秒 | 400 写（WAL + BRIN 友好） | 15 MB/s 持续写 |
| 月末报表（重查询） | 并发 20 只读 | 10000 随机读 | 200 MB/s 读 |
| 备份（全量 10 TB 集群） | — | 顺序 600 MB/s | 600 MB/s |

### NVMe 验证

4TB PCIe 4.0 NVMe 典型：7000/5500 MB/s，1M/1M IOPS → 满足峰值要求 10 倍冗余。

---

## 6. 总结

| 维度 | 单租户 5 年 SSD 需求 | 10 租户总需求 | macOS 单机推荐 |
| --- | --- | --- | --- |
| 存储 | **~10 TB SSD（含索引/WAL/预留）** | **100 TB SSD** | 4 TB NVMe + 8 TB 备份盘 |
| 内存 | 32 GB（最低），建议 64 GB | 256 GB / 主库 | 64 GB |
| 备份策略 | 3-2-1 + PITR | 3-2-1 + 异地复制 | 外挂 HDD + 本地对象存储（MinIO） |
| RPO / RTO | ≤ 15 min / ≤ 30 min | 同 | 同 |
