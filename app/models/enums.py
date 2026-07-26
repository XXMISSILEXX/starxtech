from enum import Enum


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    VIEWER_ADMIN = "VIEWER_ADMIN"
    # Legacy values retained only for migrations and compatibility fixtures.
    PROJECT_MANAGER = "PROJECT_MANAGER"
    REPORTER = "REPORTER"


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectContractorRole(str, Enum):
    CONSTRUCTION = "CONSTRUCTION"
    SOLUTION = "SOLUTION"


class ProjectContractorAssignmentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ENDED = "ENDED"


class ProjectUpdateType(str, Enum):
    GENERAL = "GENERAL"
    PROGRESS = "PROGRESS"
    HANDOVER = "HANDOVER"
    CONTRACTOR = "CONTRACTOR"
    STATUS_CHANGE = "STATUS_CHANGE"
    NOTE = "NOTE"


class DailyReportStatus(str, Enum):
    UPDATED = "UPDATED"
    GOOD = "GOOD"
    PROCESSING = "PROCESSING"
    ATTENTION = "ATTENTION"
    CRITICAL = "CRITICAL"


class SectionStatus(str, Enum):
    INFO = "INFO"
    GOOD = "GOOD"
    PROCESSING = "PROCESSING"
    ATTENTION = "ATTENTION"
    CRITICAL = "CRITICAL"


class IssueSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IssueStatus(str, Enum):
    OPEN = "OPEN"
    PROCESSING = "PROCESSING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
