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
    DRAFT = "draft"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FINAL = "final"
    FAILED = "failed"


class SocietyStatus(enum.StrEnum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    ONBOARDED = "ONBOARDED"
    INVITATION_SENT = "INVITATION_SENT"
    REPORT_PENDING = "REPORT_PENDING"
    TENDER_PENDING = "TENDER_PENDING"
    TENDER_PUBLISHED = "TENDER_PUBLISHED"
    TENDER_REVIEW_PENDING = "TENDER_REVIEW_PENDING"
    BUILDER_FINALIZED = "BUILDER_FINALIZED"
    MANUAL_PROCESS = "MANUAL_PROCESS"


class TenderStatus(enum.StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    AWARDED = "awarded"
