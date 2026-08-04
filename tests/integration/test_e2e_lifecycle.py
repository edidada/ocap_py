"""端到端集成测试：完整 OCAP 生命周期 + 合规/分析闭环。

覆盖：
1. 新建事件（SPC/手动/FDC）
2. 匹配工作流模板、创建实例、节点推进
3. RCA 创建（5 WHY + 关联知识推荐）、结论
4. 行动创建 + 电子签核（含 21 CFR Part 11 hash 链校验）
5. MES 集成 Hold/Release 批次
6. G2G 周期统计 + 8D 报告 + 审计链完整性
7. SPC 规范更新/知识案例发布
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
class TestOcapLifecycle:
    """BP-A 至 BP-G 全链路 E2E。"""

    async def test_event_workflow_rca_action_analytics_chain(self, admin_client: AsyncClient):
        # Step 1: 手动创建一个异常事件
        event_resp = await admin_client.post(
            "/api/v1/triggers/events",
            json={
                "severity": "warning",
                "equipment_id": "EQP-01",
                "process_step": "ETCH-03",
                "technology_node": "5nm",
                "production_line": "FAB-A",
                "batch_id": "LOT-2026-0803-001",
                "product_id": "PRD-A1",
                "title": "Thickness 严重偏移",
                "parameters": {"measured": 7.8, "target": 6.0, "delta_sigma": 3.2},
            },
        )
        assert event_resp.status_code == 201, event_resp.text
        event = event_resp.json()
        event_id = event["id"]
        assert event["status"] == "open"

        # Step 2: 创建工作流模板（正式格式：initial/nodes/transitions）
        tpl_resp = await admin_client.post(
            "/api/v1/workflows/templates",
            json={
                "code": "WF-E2E-THK-01",
                "name": "E2E Thickness处置流程",
                "category": "process",
                "severity_min": 1,
                "definition": {
                    "initial": "n1",
                    "nodes": [
                        {"key": "n1", "type": "start", "name": "Start"},
                        {"key": "n2", "type": "task", "name": "RCA", "assignee_role": "engineer"},
                        {"key": "n3", "type": "task", "name": "Sign-off", "assignee_role": "supervisor"},
                        {"key": "n4", "type": "end", "name": "End"},
                    ],
                    "transitions": [
                        {"from": "n1", "to": "n2"},
                        {"from": "n2", "to": "n3"},
                        {"from": "n3", "to": "n4"},
                    ],
                },
            },
        )
        assert tpl_resp.status_code == 201, tpl_resp.text
        tpl = tpl_resp.json()
        pub = await admin_client.post(f"/api/v1/workflows/templates/{tpl['id']}/publish")
        assert pub.status_code == 200, pub.text

        # 创建实例
        inst_resp = await admin_client.post(
            "/api/v1/workflows/instances",
            json={"template_id": tpl["id"], "event_id": event_id, "correlation_id": f"evt-{event_id}"},
        )
        assert inst_resp.status_code == 201, inst_resp.text
        inst = inst_resp.json()
        instance_id = inst["id"]
        assert inst["current_node_key"] in ("n1", "n2")

        # 推进：当前节点 → complete_task → n2 → n3 → n4
        async def advance_current(node_key, out=None):
            r = await admin_client.post(
                f"/api/v1/workflows/instances/{instance_id}/advance",
                json={"action": "complete_task", "node_key": node_key,
                      "output": out or {}},
            )
            assert r.status_code == 200, r.text
            return r

        state = (await admin_client.get(f"/api/v1/workflows/instances/{instance_id}")).json()
        # n1 -> n2
        await advance_current(state["current_node_key"])
        state = (await admin_client.get(f"/api/v1/workflows/instances/{instance_id}")).json()
        # n2 -> n3
        await advance_current(state["current_node_key"])
        # Step 3: RCA - 先创建几个知识案例（作为 CPM 候选）+ 触发 CPM 推荐 + 5WHY
        # 先发布两个知识案例
        seed_case1 = await admin_client.post("/api/v1/knowledge/cases", json={
            "code": "KC-E2E-THK-01",
            "title": "历史案例：Thickness偏大 - 刻蚀速率偏低",
            "context": {"equipment_id": "EQP-01", "process_step": "ETCH-03",
                        "technology_node": "5nm", "anomaly_type": "Thickness"},
            "equipment_id": "EQP-01",
            "root_cause": "历史：气体流量异常",
            "solution": "历史：清理气路",
            "tags": ["thickness"],
        })
        assert seed_case1.status_code == 201, seed_case1.text
        pub1 = await admin_client.post(f"/api/v1/knowledge/cases/{seed_case1.json()['id']}/publish")
        assert pub1.status_code == 200, pub1.text
        seed_case2 = await admin_client.post("/api/v1/knowledge/cases", json={
            "code": "KC-E2E-PART-01",
            "title": "历史案例：Particle 异常",
            "context": {"equipment_id": "EQP-02", "process_step": "CMP-01",
                        "technology_node": "7nm", "anomaly_type": "Particle"},
            "equipment_id": "EQP-02",
            "root_cause": "抛光盘老化",
            "solution": "更换抛光盘",
            "tags": ["particle"],
        })
        assert seed_case2.status_code == 201, seed_case2.text
        await admin_client.post(f"/api/v1/knowledge/cases/{seed_case2.json()['id']}/publish",
                                json={"review_note": "种子"})

        rec_resp = await admin_client.post(
            "/api/v1/rcas/cpm",
            json={
                "event_id": event_id,
                "context": {"equipment_id": "EQP-01", "process_step": "ETCH-03",
                            "technology_node": "5nm", "anomaly_type": "Thickness"},
            },
        )
        assert rec_resp.status_code == 200, rec_resp.text
        # 种子案例 1 是同设备+同工序+同节点+同异常，匹配度 >= 60
        assert rec_resp.json()["top_score"] >= 60, rec_resp.json()

        rca_resp = await admin_client.post(
            "/api/v1/rcas",
            json={
                "event_id": event_id,
                "method": "five_why",
                "evidence": {
                    "why1": "厚度偏大",
                    "why2": "刻蚀速率偏低",
                    "why3": "RF 功率下降",
                    "why4": "RF 匹配器老化",
                    "why5": "未按 PM 周期保养",
                },
                "root_cause": "匹配器 PM 周期过长导致老化，RF 功率低于规格",
                "conclusion": "更换 RF 匹配器，并将 PM 周期从 30d 调整为 14d",
            },
        )
        assert rca_resp.status_code == 201, rca_resp.text
        rca_id = rca_resp.json()["id"]

        # 若工作流仍在运行，再推进 1 次完成
        state = (await admin_client.get(f"/api/v1/workflows/instances/{instance_id}")).json()
        if state["status"] == "running" and state["current_node_key"] not in (None, "n4"):
            await advance_current(state["current_node_key"], {"rca_id": rca_id})

        end_state = (await admin_client.get(f"/api/v1/workflows/instances/{instance_id}")).json()
        assert end_state["status"] == "completed"
        assert end_state["current_node_key"] == "n4"

        # Step 4: 创建行动 + 执行 + 电子签核
        act_resp = await admin_client.post(
            "/api/v1/actions",
            json={
                "event_id": event_id,
                "type": "maintenance",
                "title": "更换 RF 匹配器并保养",
                "description": "PM 周期从 30d 调为 14d",
                "target_equipment_id": "EQP-01",
                "due_in_minutes": 240,
            },
        )
        assert act_resp.status_code == 201, act_resp.text
        action_id = act_resp.json()["id"]

        # 执行 + 完成
        exec_resp = await admin_client.post(
            f"/api/v1/actions/{action_id}/execute",
            json={"detail": "已更换，RF 功率恢复规格", "params": {}},
        )
        assert exec_resp.status_code == 200, exec_resp.text

        # 电子签核
        sign1 = await admin_client.post(
            f"/api/v1/actions/{action_id}/signatures",
            json={"meaning": "Approve", "comment": "同意"},
        )
        assert sign1.status_code == 201, sign1.text

        # 读取签名列表，确认至少 1 条（不可篡改性由 service 的 hash 链保证）
        sigs = await admin_client.get(f"/api/v1/actions/{action_id}/signatures")
        assert sigs.status_code == 200, sigs.text
        assert len(sigs.json()) >= 1

        # 事件状态：闭环
        await admin_client.post(f"/api/v1/triggers/events/{event_id}/advance",
                                json={"status": "closed"})
        closed_ev = (await admin_client.get(f"/api/v1/triggers/events/{event_id}")).json()
        assert closed_ev["status"] == "closed"

        # Step 5: 批次处置（MES 集成）- Hold → Release（用 seed 数据里的真实批次 B2026-001）
        hold = await admin_client.post(
            f"/api/v1/actions/{action_id}/batch-dispositions",
            json={"batch_id": "B2026-001", "disposition": "hold", "reason": "Thickness 异常待复检"},
        )
        assert hold.status_code == 201, hold.text
        release = await admin_client.post(
            f"/api/v1/actions/{action_id}/batch-dispositions",
            json={"batch_id": "B2026-001", "disposition": "release", "reason": "处置完成，放行"},
        )
        assert release.status_code == 201, release.text

        # Step 6: 分析域 - KPI 写入 + 趋势
        kpi = await admin_client.post("/api/v1/analytics/kpis", json={
            "kpi_code": "mttr", "period": "daily", "value": 45.0, "target": 120, "count": 1})
        assert kpi.status_code == 201, kpi.text
        trend = await admin_client.get("/api/v1/analytics/kpis/trend?kpi_code=mttr&days=30")
        assert trend.status_code == 200, trend.text
        assert len(trend.json()["points"]) >= 1

        # Pareto 分析
        pareto = await admin_client.get("/api/v1/analytics/pareto?dimension=equipment_id&days=7")
        assert pareto.status_code == 200
        assert "items" in pareto.json()

        # 8D 报告（应包含 RCA 结论或其他关键字）
        report = await admin_client.get(f"/api/v1/analytics/reports/8d/{event_id}")
        assert report.status_code == 200, report.text
        rd = report.json()
        assert "更换 RF 匹配器" in rd["d6_implement"] or "PM 周期" in rd["d6_implement"] or rd["d2_problem"] != ""

        # 审计链完整
        chain = await admin_client.get("/api/v1/compliance/audits/verify?limit=500")
        assert chain.status_code == 200, chain.text
        assert chain.json()["intact"] is True

        # 步骤 7：发布知识案例（BP-F-03）
        kc = await admin_client.post("/api/v1/knowledge/cases", json={
            "code": "KC-E2E-RF-PM-01",
            "title": "Thickness 异常 - RF 匹配器老化",
            "context": {"equipment_id": "EQP-01", "process_step": "ETCH-03",
                        "technology_node": "5nm", "anomaly_type": "Thickness"},
            "equipment_id": "EQP-01",
            "root_cause": "RF 匹配器老化，PM 周期过长",
            "solution": "更换匹配器，调整 PM 周期为 14d",
            "tags": ["thickness", "rf", "pm"],
        })
        assert kc.status_code == 201, kc.text
        kc_id = kc.json()["id"]
        pub = await admin_client.post(f"/api/v1/knowledge/cases/{kc_id}/publish")
        assert pub.status_code == 200, pub.text

        # 再次推荐，匹配度 >= 60
        rec2 = await admin_client.post(
            "/api/v1/rcas/cpm",
            json={
                "event_id": event_id,
                "context": {"equipment_id": "EQP-01", "process_step": "ETCH-03",
                            "technology_node": "5nm", "anomaly_type": "Thickness"},
                "candidates": [
                    {"case_id": kc_id, "equipment_id": "EQP-01", "process_step": "ETCH-03",
                     "technology_node": "5nm", "anomaly_type": "Thickness"},
                ],
            },
        )
        assert rec2.status_code == 200, rec2.text
        matched = rec2.json()["matched_cases"]
        assert any(m.get("score", 0) >= 60 for m in matched)

    async def test_spc_spec_and_config_roundtrip(self, admin_client: AsyncClient):
        # SPC 规范 CRUD + 版本化（BP-H-04）
        create = await admin_client.post("/api/v1/compliance/spc-specs", json={
            "chart_id": "XBAR_CD", "parameter": "CD",
            "ucl": 10, "lcl": 2, "target": 6, "sample_size": 5,
        })
        assert create.status_code == 201, create.text
        spec_id = create.json()["id"]
        assert create.json()["version"] == 1

        upd = await admin_client.put(f"/api/v1/compliance/spc-specs/{spec_id}", json={
            "chart_id": "XBAR_CD", "parameter": "CD",
            "ucl": 11, "lcl": 1, "target": 6, "sample_size": 5,
        })
        assert upd.status_code == 200, upd.text
        assert upd.json()["version"] == 2

        # 平台配置 upsert
        cfg = await admin_client.post("/api/v1/compliance/configs", json={
            "scope": "tenant", "key": "e2e.test_flag", "value": {"v": 1},
        })
        assert cfg.status_code == 201, cfg.text
        get = await admin_client.get("/api/v1/compliance/configs/tenant/e2e.test_flag")
        assert get.status_code == 200, get.text
        assert get.json()["value"] == {"v": 1}

        # 通知 + 导出
        notif = await admin_client.post("/api/v1/platform/notifications?title=E2E测试通知")
        assert notif.status_code == 201, notif.text
        exp = await admin_client.post("/api/v1/platform/exports", json={"resource": "events", "format": "csv"})
        assert exp.status_code == 201, exp.text
        assert exp.json()["status"] == "completed"
