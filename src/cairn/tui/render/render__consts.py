from cairn.domain import ArtifactType, EntityType, IssueKind

# Glyphs keyed by artifact type for compact sidebar/list rendering.
ARTIFACT_ICONS: dict[ArtifactType, str] = {
    ArtifactType.CAMPAIGN_STATE: "📣",
    ArtifactType.PRICING_POLICY: "💲",
    ArtifactType.ACCOUNT_INTELLIGENCE: "🏢",
    ArtifactType.CUSTOMER_PROFILE: "👤",
    ArtifactType.EXPANSION_STRATEGY: "🧭",
    ArtifactType.RISK_ASSESSMENT: "⚠️",
    ArtifactType.EXECUTION_PLAN: "🗂️",
    ArtifactType.ORG_SUMMARY: "🏛️",
    ArtifactType.WIKI_PAGE: "📖",
    ArtifactType.GENERIC: "📄",
}
DEFAULT_ARTIFACT_ICON = "📄"

ENTITY_ICONS: dict[EntityType, str] = {
    EntityType.PERSON: "👤",
    EntityType.ORGANIZATION: "🏢",
    EntityType.PRODUCT: "📦",
    EntityType.PROJECT: "🗂️",
    EntityType.REGION: "🌍",
    EntityType.INDUSTRY: "🏭",
    EntityType.POLICY: "📜",
    EntityType.DECISION: "✔️",
    EntityType.RISK: "⚠️",
}
DEFAULT_ENTITY_ICON = "•"

# Severity → colour for evaluation issues (Rich style names).
SEVERITY_STYLES: tuple[tuple[float, str], ...] = (
    (0.66, "red"),
    (0.33, "yellow"),
    (0.0, "blue"),
)

ISSUE_LABELS: dict[IssueKind, str] = {
    IssueKind.STALE: "stale",
    IssueKind.LOW_CONFIDENCE: "low confidence",
    IssueKind.CONTRADICTION: "contradiction",
    IssueKind.UNREFERENCED: "unreferenced",
}

# Cap how many items the sidebar lists before summarising the remainder.
MAX_SIDEBAR_ITEMS = 12

__all__ = [
    "ARTIFACT_ICONS",
    "DEFAULT_ARTIFACT_ICON",
    "DEFAULT_ENTITY_ICON",
    "ENTITY_ICONS",
    "ISSUE_LABELS",
    "MAX_SIDEBAR_ITEMS",
    "SEVERITY_STYLES",
]
