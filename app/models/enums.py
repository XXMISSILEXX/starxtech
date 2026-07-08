from enum import Enum


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    VIEWER_ADMIN = "VIEWER_ADMIN"
    REPORTER = "REPORTER"


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


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
