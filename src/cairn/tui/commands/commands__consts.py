from cairn.domain import ArtifactType, EntityType, IssueKind
from cairn.tui.serialize import ARTIFACT_FIELDS, ENTITY_FIELDS

from .commands__types import CommandSpec, FlagSpec, FlagType

# UI side-effect actions a command can request from the app.
ACTION_CLEAR = "clear"
ACTION_QUIT = "quit"

PROCESS_DEFAULT_TYPE = ArtifactType.ACCOUNT_INTELLIGENCE

_ARTIFACT_TYPES = tuple(t.value for t in ArtifactType)
_ENTITY_TYPES = tuple(t.value for t in EntityType)
_ISSUE_KINDS = tuple(k.value for k in IssueKind)
_ARTIFACT_FIELD_CHOICES = tuple(ARTIFACT_FIELDS)
_ENTITY_FIELD_CHOICES = tuple(ENTITY_FIELDS)

_FIELDS_HELP = "comma-separated fields to include in json output"

# Single source of truth for the command surface: drives dispatch lookup,
# flag parsing, `/help` (rich and json), and the footer hint. Every command
# additionally accepts --format rich|plain|json (appended by the parser).
COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("help", "[command]", "show this help (or one command's flags in detail)"),
    CommandSpec("ingest", "<text>", "buffer a document from inline text"),
    CommandSpec("load", "<path>", "buffer a document from a file"),
    CommandSpec(
        "process",
        "",
        "extract & compile buffered docs into artifacts",
        flags=(
            FlagSpec(
                "type",
                FlagType.STR,
                "artifact type to compile",
                default=PROCESS_DEFAULT_TYPE.value,
                choices=_ARTIFACT_TYPES,
            ),
        ),
    ),
    CommandSpec(
        "query",
        "<intent>",
        "assemble runtime context (or just type text)",
        flags=(
            FlagSpec("budget", FlagType.INT, "token budget (default: session budget)"),
            FlagSpec(
                "types",
                FlagType.CSV,
                "restrict to artifact types",
                default=(),
                choices=_ARTIFACT_TYPES,
            ),
            FlagSpec("hints", FlagType.CSV, "entity name hints to bias retrieval", default=()),
            FlagSpec("min-conf", FlagType.FLOAT, "minimum fragment confidence", default=0.0),
            FlagSpec("max-age", FlagType.INT, "max artifact age in days"),
            FlagSpec("top-k", FlagType.INT, "max artifacts to retrieve", default=10),
            FlagSpec("depth", FlagType.INT, "graph traversal depth", default=1),
        ),
    ),
    CommandSpec(
        "artifacts",
        "",
        "list compiled artifacts",
        flags=(
            FlagSpec("type", FlagType.STR, "filter by artifact type", choices=_ARTIFACT_TYPES),
            FlagSpec("entity", FlagType.STR, "filter by entity id or name"),
            FlagSpec("min-conf", FlagType.FLOAT, "minimum confidence", default=0.0),
            FlagSpec("limit", FlagType.INT, "max rows"),
            FlagSpec("all", FlagType.BOOL, "include superseded artifacts", default=False),
            FlagSpec("fields", FlagType.CSV, _FIELDS_HELP, choices=_ARTIFACT_FIELD_CHOICES),
        ),
    ),
    CommandSpec(
        "artifact",
        "<id>",
        "show one artifact in full (id prefix is enough)",
        flags=(FlagSpec("fields", FlagType.CSV, _FIELDS_HELP, choices=_ARTIFACT_FIELD_CHOICES),),
    ),
    CommandSpec(
        "entities",
        "",
        "list resolved entities",
        flags=(
            FlagSpec("type", FlagType.STR, "filter by entity type", choices=_ENTITY_TYPES),
            FlagSpec("name", FlagType.STR, "case-insensitive substring of name/aliases"),
            FlagSpec("limit", FlagType.INT, "max rows"),
            FlagSpec("fields", FlagType.CSV, _FIELDS_HELP, choices=_ENTITY_FIELD_CHOICES),
        ),
    ),
    CommandSpec("wiki", "", "(re)generate entity wiki pages"),
    CommandSpec(
        "eval",
        "",
        "run knowledge-quality checks",
        flags=(
            FlagSpec(
                "contradictions", FlagType.BOOL, "also check for contradictions", default=False
            ),
            FlagSpec("min-severity", FlagType.FLOAT, "minimum issue severity", default=0.0),
            FlagSpec("kind", FlagType.STR, "filter by issue kind", choices=_ISSUE_KINDS),
        ),
    ),
    CommandSpec("seed", "", "load demo data for offline exploration"),
    CommandSpec("clear", "", "clear the transcript"),
    CommandSpec("quit", "", "exit cairn"),
)

__all__ = ["ACTION_CLEAR", "ACTION_QUIT", "COMMANDS", "PROCESS_DEFAULT_TYPE"]
