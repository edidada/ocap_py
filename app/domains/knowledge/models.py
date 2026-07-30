"""BP-F 知识管理域 ORM 模型。

支撑：OCAP 案例库(BP-F-01)、经验复用(BP-F-03)、处置方案模板库(BP-F-04)、
知识版本管理(BP-F-06)。知识图谱(BP-F-02)/专家经验数字化(BP-F-05) P2 提供模型占位。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import BigIntVariant, JSONBCompat
from app.db.base import Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin
from app.domains.common.enums import KnowledgeCaseStatus


class KnowledgeCase(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    """OCAP 历史案例（BP-F-01）。"""

    __tablename__ = "knowledge_cases"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_kcase_tenant_code"),)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    event_id: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True, index=True)
    equipment_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    process_step: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    anomaly_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False, default="")
    solution: Mapped[str] = mapped_column(Text, nullable=False, default="")
    context: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=KnowledgeCaseStatus.DRAFT.value, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[int | None] = mapped_column(BigIntVariant(), nullable=True)


class KnowledgeCaseVersion(Base, IDMixin, TimestampMixin):
    """案例版本快照（BP-F-06）。"""

    __tablename__ = "knowledge_case_versions"
    case_id: Mapped[int] = mapped_column(
        BigIntVariant(), ForeignKey("knowledge_cases.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    change_log: Mapped[str] = mapped_column(String(512), nullable=False, default="")


class SolutionTemplate(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    """处置方案模板库（BP-F-04）。"""

    __tablename__ = "solution_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_soln_tenant_code"),)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    anomaly_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    steps: Mapped[list] = mapped_column(JSONBCompat, nullable=False, default=list)
    applicable_context: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True)


class KnowledgeGraphNode(Base, IDMixin, TenantMixin, TimestampMixin):
    """知识图谱节点（BP-F-02，P2）。"""

    __tablename__ = "knowledge_graph_nodes"
    node_type: Mapped[str] = mapped_column(String(32), nullable=False)  # equipment/process/parameter/anomaly/cause
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attributes: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)


class KnowledgeGraphEdge(Base, IDMixin, TenantMixin, TimestampMixin):
    """知识图谱边（BP-F-02，P2）。"""

    __tablename__ = "knowledge_graph_edges"
    from_node_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("knowledge_graph_nodes.id"), nullable=False)
    to_node_id: Mapped[int] = mapped_column(BigIntVariant(), ForeignKey("knowledge_graph_nodes.id"), nullable=False)
    relation: Mapped[str] = mapped_column(String(32), nullable=False)  # causes/relates_to/measures
    weight: Mapped[float] = mapped_column(nullable=False, default=1.0)


class ExpertRule(Base, IDMixin, TenantMixin, TimestampMixin, VersionMixin):
    """专家经验数字化规则（BP-F-05，P2）。"""

    __tablename__ = "expert_rules"
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    condition: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, default=dict)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.8)
    enabled: Mapped[bool] = mapped_column(default=True)
