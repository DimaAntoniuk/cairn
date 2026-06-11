from .commands__types import CommandSpec

# UI side-effect actions a command can request from the app.
ACTION_CLEAR = "clear"
ACTION_QUIT = "quit"

# Single source of truth for the command surface: drives dispatch lookup,
# `/help`, and the footer hint.
COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("help", "", "show this help"),
    CommandSpec("ingest", "<text>", "buffer a document from inline text"),
    CommandSpec("load", "<path>", "buffer a document from a file"),
    CommandSpec("process", "[type]", "extract & compile buffered docs into artifacts"),
    CommandSpec("query", "<intent>", "assemble runtime context (or just type text)"),
    CommandSpec("artifacts", "", "list compiled artifacts"),
    CommandSpec("artifact", "<id>", "show one artifact in full"),
    CommandSpec("entities", "", "list resolved entities"),
    CommandSpec("wiki", "", "(re)generate entity wiki pages"),
    CommandSpec("eval", "[contradictions]", "run knowledge-quality checks"),
    CommandSpec("seed", "", "load demo data for offline exploration"),
    CommandSpec("clear", "", "clear the transcript"),
    CommandSpec("quit", "", "exit cairn"),
)

__all__ = ["ACTION_CLEAR", "ACTION_QUIT", "COMMANDS"]
