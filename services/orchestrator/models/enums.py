"""Shared enums used across models."""

import enum


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    PMC = "pmc"
    SOCIETY = "society"
    BUILDER = "builder"
    LAWYER = "lawyer"
    VIEWER = "viewer"


class EnquiryStatus(enum.StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class InviteStatus(enum.StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


class ReportStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TenderStatus(enum.StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    AWARDED = "awarded"


