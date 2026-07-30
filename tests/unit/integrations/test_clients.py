"""集成注册表与各 fake 客户端测试。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.exceptions import NotFoundError
from app.integrations.dtos import FdcAlarmDTO, SpcEventDTO
from app.integrations.fake.store import FakeStore
from app.integrations.registry import IntegrationRegistry


@pytest.mark.unit
class TestRegistry:
    def test_get_returns_client_per_system(self, fake_integrations):
        spc = fake_integrations.get("spc")
        assert spc.system_code == "spc"
        mes = fake_integrations.get("mes")
        assert mes.system_code == "mes"
        # 同一系统返回同一实例（缓存）
        assert fake_integrations.get("spc") is spc

    def test_all_clients_share_store(self, fake_integrations):
        spc = fake_integrations.get("spc")
        mes = fake_integrations.get("mes")
        assert spc.store is mes.store

    def test_unsupported_system_raises(self, fake_integrations):
        with pytest.raises(NotFoundError):
            fake_integrations.get("unknown")

    def test_supported_systems(self, fake_integrations):
        systems = fake_integrations.supported_systems()
        assert {"spc", "fdc", "mes", "ams", "sfmm", "yms", "dms", "apc", "recipe"} <= set(systems)

    async def test_from_seed_loads_data(self):
        reg = IntegrationRegistry.from_seed()
        spc = reg.get("spc")
        events = await spc.fetch_ooc_events()
        assert len(events) >= 1


@pytest.mark.unit
class TestSpcClient:
    async def test_fetch_and_record(self, fake_integrations):
        spc = fake_integrations.get("spc")
        events = await spc.fetch_ooc_events()
        assert any(e.event_id == "SE-001" for e in events)
        new_event = SpcEventDTO(
            event_id="SE-NEW",
            chart_id="C-THK-01",
            parameter="thickness",
            value=108.0,
            violation="UCL_EXCEEDED",
            detected_at=datetime.now(timezone.utc),
            severity="critical",
        )
        await spc.record_event(new_event)
        chart = await spc.get_chart("C-THK-01")
        assert chart.last_value == 108.0
        assert chart.last_ooc_at is not None


@pytest.mark.unit
class TestFdcClient:
    async def test_fetch_and_raise(self, fake_integrations):
        fdc = fake_integrations.get("fdc")
        alarms = await fdc.fetch_alarms()
        assert any(a.alarm_id == "FA-001" for a in alarms)
        new_alarm = FdcAlarmDTO(
            alarm_id="FA-NEW",
            equipment_id="EQP-X",
            fault="temp_drift",
            detected_at=datetime.now(timezone.utc),
        )
        await fdc.raise_alarm(new_alarm)
        assert await fdc.get_alarm("FA-NEW") is not None

    async def test_filter_by_equipment(self, fake_integrations):
        fdc = fake_integrations.get("fdc")
        alarms = await fdc.fetch_alarms(equipment_id="EQP-ETCH-01")
        assert all(a.equipment_id == "EQP-ETCH-01" for a in alarms)


@pytest.mark.unit
class TestMesClient:
    async def test_hold_release_scrap(self, fake_integrations):
        mes = fake_integrations.get("mes")
        held = await mes.hold_batch("B2026-001", "OOC")
        assert held.success and held.new_status == "held"
        released = await mes.release_batch("B2026-001", "resolved")
        assert released.new_status == "released"
        scrapped = await mes.scrap_batch("B2026-001", "unrepairable")
        assert scrapped.new_status == "scrapped"

    async def test_get_batch_not_found(self, fake_integrations):
        mes = fake_integrations.get("mes")
        with pytest.raises(NotFoundError):
            await mes.get_batch("NOPE")


@pytest.mark.unit
class TestAmsClient:
    async def test_fetch_uncleared_and_clear(self, fake_integrations):
        ams = fake_integrations.get("ams")
        alarms = await ams.fetch_alarms()
        assert all(a.cleared_at is None for a in alarms)
        cleared = await ams.clear_alarm("AA-001")
        assert cleared is True
        remaining = await ams.fetch_alarms()
        assert all(a.alarm_id != "AA-001" for a in remaining)


@pytest.mark.unit
class TestSfmmClient:
    async def test_create_and_complete(self, fake_integrations):
        sfmm = fake_integrations.get("sfmm")
        order = await sfmm.create_maintenance_order("EQP-ETCH-01", "corrective")
        assert order.status == "open"
        completed = await sfmm.complete_order(order.order_id)
        assert completed.status == "done"


@pytest.mark.unit
class TestYmsClient:
    async def test_fetch_and_record(self, fake_integrations):
        yms = fake_integrations.get("yms")
        yields = await yms.fetch_yields()
        assert any(y.batch_id == "B2026-004" for y in yields)
        await yms.record_yield(
            (await yms.fetch_yields("B2026-004"))[0].model_copy(update={"yield_rate": 99.0})
        )
        updated = await yms.fetch_yields("B2026-004")
        assert updated[0].yield_rate == 99.0


@pytest.mark.unit
class TestDmsClient:
    async def test_fetch_defects(self, fake_integrations):
        dms = fake_integrations.get("dms")
        defects = await dms.fetch_defects()
        assert len(defects) >= 1
        filtered = await dms.fetch_defects("B2026-001")
        assert all(d.batch_id == "B2026-001" for d in filtered)


@pytest.mark.unit
class TestApcClient:
    async def test_model_status(self, fake_integrations):
        apc = fake_integrations.get("apc")
        status = await apc.get_model_status("EQP-ETCH-01")
        assert status["in_range"] is True
        await apc.set_model_out_of_range("EQP-ETCH-01")
        status = await apc.get_model_status("EQP-ETCH-01")
        assert status["in_range"] is False


@pytest.mark.unit
class TestRecipeClient:
    async def test_change_and_revert(self, fake_integrations):
        recipe = fake_integrations.get("recipe")
        original = await recipe.get_recipe("R-ETCH-001")
        old_version = original.version
        old_params = dict(original.params)
        changed = await recipe.change_recipe("R-ETCH-001", {"power": 1600})
        assert changed.success and changed.new_version == old_version + 1
        assert (await recipe.get_recipe("R-ETCH-001")).params["power"] == 1600
        await recipe.revert_recipe("R-ETCH-001", old_params)
        assert (await recipe.get_recipe("R-ETCH-001")).params["power"] == 1500

    async def test_get_recipe_not_found(self, fake_integrations):
        recipe = fake_integrations.get("recipe")
        with pytest.raises(NotFoundError):
            await recipe.get_recipe("NOPE")
