"""跨域枚举定义。所有域共享的枚举集中在此，域专属枚举可在域内定义。"""

from __future__ import annotations

import enum


class EventSource(str, enum.Enum):
    """异常事件来源。"""

    SPC = "spc"
    FDC = "fdc"
    EQUIPMENT = "equipment"
    APC = "apc"
    YIELD = "yield"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class Severity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


class EventStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    MERGED = "merged"
    RESOLVED = "resolved"
    CLOSED = "closed"


class WorkflowTemplateStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class WorkflowInstanceStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    SUSPENDED = "suspended"


class InterventionType(str, enum.Enum):
    SKIP = "skip"
    JUMP = "jump"
    REASSIGN = "reassign"
    OVERRIDE = "override"
    ESCALATION = "escalation"


class ActionType(str, enum.Enum):
    HOLD = "hold"
    RELEASE = "release"
    SCRAP = "scrap"
    REWORK = "rework"
    RECIPE_CHANGE = "recipe_change"
    MAINTENANCE = "maintenance"
    SCRIPT = "script"
    MANUAL = "manual"


class ActionStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class BatchDisposition(str, enum.Enum):
    HOLD = "hold"
    RELEASE = "release"
    SCRAP = "scrap"
    REWORK = "rework"


class RcaStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    CONCLUDED = "concluded"


class RcaMethod(str, enum.Enum):
    FIVE_WHY = "five_why"
    FISHBONE = "fishbone"
    FTA = "fta"
    CPM = "cpm"
    DATA_CORRELATION = "data_correlation"


class KnowledgeCaseStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class KpiCode(str, enum.Enum):
    MTTR = "mttr"
    CLOSURE_RATE = "closure_rate"
    RECURRENCE_RATE = "recurrence_rate"
    HUMAN_ERROR_RATE = "human_error_rate"
    G2G_CYCLE = "g2g_cycle"
    RAM_AVAILABILITY = "ram_availability"


class Period(str, enum.Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SIGN = "sign"
    ADVANCE = "advance"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"


class IntegrationSystem(str, enum.Enum):
    SPC = "spc"
    FDC = "fdc"
    MES = "mes"
    AMS = "ams"
    SFMM = "sfmm"
    YMS = "yms"
    DMS = "dms"
    APC = "apc"
    RECIPE = "recipe"


class IntegrationMode(str, enum.Enum):
    MOCK = "mock"
    LIVE = "live"


class SyncDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class DataQualityMetric(str, enum.Enum):
    COMPLETENESS = "completeness"
    TIMELINESS = "timeliness"
    CONSISTENCY = "consistency"
    VALIDITY = "validity"


class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    IM = "im"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class RoleCode(str, enum.Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    SUPERVISOR = "supervisor"
    OPERATOR = "operator"
    AUDITOR = "auditor"


class TenantStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class ConfigItemScope(str, enum.Enum):
    GLOBAL = "global"
    TENANT = "tenant"
