from textual.binding import BindingType

# Textual CSS for the app. Sidebar width is applied in code from
# session__consts.SIDEBAR_WIDTH to keep a single source of truth.
CSS = """
#body {
    height: 1fr;
}
#transcript {
    width: 2fr;
    height: 100%;
    border: round $primary;
    padding: 0 1;
}
#sidebar {
    height: 100%;
    border: round $secondary;
    padding: 0 1;
}
#sidebar > Static {
    margin-bottom: 1;
}
#prompt {
    border: round $accent;
}
"""

INTRO = (
    "[b]cairn[/b] — agent knowledge layer\n"
    "[dim]type a question to query · /help for commands · /seed for demo data[/dim]"
)

PROMPT_PLACEHOLDER = "ask a question, or /help …"

BINDINGS: list[BindingType] = [
    ("ctrl+l", "clear", "Clear"),
    ("ctrl+c", "quit", "Quit"),
]

__all__ = ["BINDINGS", "CSS", "INTRO", "PROMPT_PLACEHOLDER"]
