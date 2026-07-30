"""触发域服务测试（DB）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.domains.common.enums import EventSource, EventStatus, Severity
from app.domains.trigger import service
from app.domains.trigger.schemas import (
    EventAdvance,
    EventCreate,
    EventIngest,
    TriggerRuleCreate,
    TriggerRuleUpdate,
)

TENANT = 1
T0 = datetime(2026, 7, 30, 8, 30, tzinfo=timezone.utc)


@pytest.mark.unit
class TestEventService:
    async def test_create_event(self, seeded_db):
        event = await service.create_event(
            seeded_db,
            TENANT,
            EventCreate(
                source=EventSource.SPC,
                severity=Severity.CRITICAL,
                equipment_id="EQP-01",
                detected_at=T0,
                title="厚度超限",
            ),
        )
        await seeded_db.flush()
        assert event.id is not None
        assert event.status == EventStatus.OPEN.value
        assert event.severity == Severity.CRITICAL.value

    async def test_get_event_not_found(self, seeded_db):
        with pytest.raises(NotFoundError):
            await service.get_event(seeded_db, TENANT, 9999)

    async def test_get_event_wrong_tenant(self, seeded_db):
        event = await service.create_event(
            seeded_db, TENANT, EventCreate(source=EventSource.MANUAL, detected_at=T0)
        )
        await seeded_db.flush()
        with pytest.raises(NotFoundError):
            await service.get_event(seeded_db, 999, event.id)

    async def test_advance_status(self, seeded_db):
        event = await service.create_event(
            seeded_db, TENANT, EventCreate(source=EventSource.MANUAL, detected_at=T0)
        )
        await seeded_db.flush()
        advanced = await service.advance_event(
            seeded_db, TENANT, event.id, EventAdvance(status=EventStatus.IN_PROGRESS)
        )
        assert advanced.status == EventStatus.IN_PROGRESS.value
        # 非法迁移
        with pytest.raises(ConflictError):
            await service.advance_event(
                seeded_db, TENANT, event.id, EventAdvance(status=EventStatus.OPEN)
            )

    async def test_advance_to_closed(self, seeded_db):
        event = await service.create_event(
            seeded_db, TENANT, EventCreate(source=EventSource.MANUAL, detected_at=T0)
        )
        await seeded_db.flush()
        await service.advance_event(seeded_db, TENANT, event.id, EventAdvance(status=EventStatus.CLOSED))
        # closed 之后不能再迁移
        with pytest.raises(ConflictError):
            await service.advance_event(
                seeded_db, TENANT, event.id, EventAdvance(status=EventStatus.RESOLVED)
            )


@pytest.mark.unit
class TestIngestWithRules:
    async def _create_rule(self, db, **overrides):
        defaults = dict(
            code="rule-critical-spc",
            name="SPC 严重异常",
            source=EventSource.SPC,
            condition={"severity": ["critical", "fatal"]},
            priority=10,
            debounce_window_s=0,
            dedup_key_tpl=None,
        )
        defaults.update(overrides)
        return await service.create_rule(db, TENANT, TriggerRuleCreate(**defaults))

    async def test_ingest_matches_rule(self, seeded_db):
        rule = await self._create_rule(seeded_db)
        await seeded_db.flush()
        result = await service.ingest_event(
            seeded_db,
            TENANT,
            EventIngest(
                source=EventSource.SPC,
                severity=Severity.CRITICAL,
                equipment_id="EQP-01",
                detected_at=T0,
            ),
        )
        assert result.created is True
        assert result.trigger_rule_id == rule.id

    async def test_ingest_no_match_no_rule(self, seeded_db):
        await self._create_rule(seeded_db, condition={"severity": ["fatal"]})
        await seeded_db.flush()
        result = await service.ingest_event(
            seeded_db,
            TENANT,
            EventIngest(source=EventSource.SPC, severity=Severity.WARNING, detected_at=T0),
        )
        assert result.created is True
        assert result.trigger_rule_id is None

    async def test_ingest_dedup_merge(self, seeded_db):
        await self._create_rule(
            seeded_db,
            code="rule-dedup",
            debounce_window_s=60,
            dedup_key_tpl="{equipment_id}:{source}",
        )
        await seeded_db.flush()
        first = await service.ingest_event(
            seeded_db,
            TENANT,
            EventIngest(
                source=EventSource.SPC,
                severity=Severity.CRITICAL,
                equipment_id="EQP-01",
                detected_at=T0,
            ),
        )
        assert first.created is True

        second = await service.ingest_event(
            seeded_db,
            TENANT,
            EventIngest(
                source=EventSource.SPC,
                severity=Severity.CRITICAL,
                equipment_id="EQP-01",
                detected_at=T0 + timedelta(seconds=10),
            ),
        )
        assert second.created is False
        assert second.merged_into == first.event_id
        assert second.dedup_count == 2

    async def test_ingest_dedup_window_expired(self, seeded_db):
        await self._create_rule(
            seeded_db,
            code="rule-dedup2",
            debounce_window_s=60,
            dedup_key_tpl="{equipment_id}:{source}",
        )
        await seeded_db.flush()
        await service.ingest_event(
            seeded_db,
            TENANT,
            EventIngest(source=EventSource.SPC, severity=Severity.CRITICAL, equipment_id="EQP-01", detected_at=T0),
        )
        # 超过窗口，应创建新事件
        result = await service.ingest_event(
            seeded_db,
            TENANT,
            EventIngest(
                source=EventSource.SPC,
                severity=Severity.CRITICAL,
                equipment_id="EQP-01",
                detected_at=T0 + timedelta(seconds=120),
            ),
        )
        assert result.created is True
        assert result.dedup_count == 1


@pytest.mark.unit
class TestRuleService:
    async def test_create_and_list_rule(self, seeded_db):
        rule = await service.create_rule(
            seeded_db,
            TENANT,
            TriggerRuleCreate(code="r1", source=EventSource.FDC, condition={"severity": "critical"}),
        )
        await seeded_db.flush()
        rules = await service.list_rules(seeded_db, TENANT)
        assert any(r.code == "r1" for r in rules)

    async def test_create_duplicate_code_conflict(self, seeded_db):
        await service.create_rule(
            seeded_db, TENANT, TriggerRuleCreate(code="dup", source=EventSource.SPC)
        )
        await seeded_db.flush()
        with pytest.raises(ConflictError):
            await service.create_rule(
                seeded_db, TENANT, TriggerRuleCreate(code="dup", source=EventSource.SPC)
            )

    async def test_update_rule(self, seeded_db):
        rule = await service.create_rule(
            seeded_db, TENANT, TriggerRuleCreate(code="r2", source=EventSource.SPC)
        )
        await seeded_db.flush()
        updated = await service.update_rule(
            seeded_db, TENANT, rule.id, TriggerRuleUpdate(priority=99, enabled=False)
        )
        assert updated.priority == 99
        assert updated.enabled is False

    async def test_publish_rule_creates_version(self, seeded_db):
        rule = await service.create_rule(
            seeded_db, TENANT, TriggerRuleCreate(code="r3", source=EventSource.SPC)
        )
        await seeded_db.flush()
        published = await service.publish_rule(seeded_db, TENANT, rule.id, published_by=2)
        assert published.version == 1

    async def test_get_rule_not_found(self, seeded_db):
        with pytest.raises(NotFoundError):
            await service.get_rule(seeded_db, TENANT, 9999)
