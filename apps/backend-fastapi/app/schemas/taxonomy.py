"""Clause taxonomy and shared enums."""

from enum import StrEnum


class ClauseType(StrEnum):
    """Supported clause categories (8-12 types per spec).

    This enum is the single source of truth for the taxonomy: the classifier
    prompt is built from ``[t.value for t in ClauseType]``, so adding a member
    here is all it takes to teach the pipeline a new category.
    """

    CONFIDENTIALITY = "confidentiality"  # Obligations to keep shared information secret.
    INDEMNIFICATION = "indemnification"  # One party covers losses/claims incurred by the other.
    LIMITATION_OF_LIABILITY = "limitation_of_liability"  # Caps or excludes a party's liability.
    TERMINATION = "termination"  # How and when the agreement can be ended.
    GOVERNING_LAW = "governing_law"  # Which jurisdiction's law governs the contract.
    INTELLECTUAL_PROPERTY = "intellectual_property"  # Ownership and licensing of IP.
    PAYMENT_TERMS = "payment_terms"  # Amounts, schedule, and conditions of payment.
    WARRANTY = "warranty"  # Assurances about goods/services provided.
    NON_COMPETE = "non_compete"  # Restrictions on competing activities.
    DATA_PROTECTION = "data_protection"  # Handling of personal/sensitive data.
    FORCE_MAJEURE = "force_majeure"  # Excused performance due to extraordinary events.
    OTHER = "other"  # Anything not covered by the categories above.


class RiskLevel(StrEnum):
    """Risk rating assigned to a clause."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"
