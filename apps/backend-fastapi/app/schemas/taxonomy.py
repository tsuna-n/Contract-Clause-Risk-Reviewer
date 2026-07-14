"""Clause taxonomy and shared enums."""

from enum import Enum


class ClauseType(str, Enum):
    """Supported clause categories (8-12 types per spec)."""

    CONFIDENTIALITY = "confidentiality"
    INDEMNIFICATION = "indemnification"
    LIMITATION_OF_LIABILITY = "limitation_of_liability"
    TERMINATION = "termination"
    GOVERNING_LAW = "governing_law"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    PAYMENT_TERMS = "payment_terms"
    WARRANTY = "warranty"
    NON_COMPETE = "non_compete"
    DATA_PROTECTION = "data_protection"
    FORCE_MAJEURE = "force_majeure"
    OTHER = "other"


class RiskLevel(str, Enum):
    """Risk rating assigned to a clause."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"
