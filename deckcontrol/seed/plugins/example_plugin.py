"""Example DeckControl plugin – copy this file, rename it, edit it, press "↻ Plugins" in the app.

Every function decorated with @action shows up in the "+ Add action" menu.
Whatever you put in `params` becomes a form in the editor.
Files starting with an underscore (_) are ignored.
"""
import datetime

from deckcontrol.api import action, Param


@action("example_clipboard_time", "Type current time", category="Examples", icon="🕒",
        params=[Param("fmt", "Format", "text", "%H:%M")],
        desc="Types the current time wherever the cursor is.")
def type_time(ctx, p):
    from deckcontrol.actions import kb
    kb().type(datetime.datetime.now().strftime(p["fmt"]))


@action("example_counter", "Count presses on key label", category="Examples", icon="🔢",
        desc="Shows how a plugin can change a key's label (ctx.set_label).")
def counter(ctx, p):
    ctx.engine.__dict__.setdefault("_ex_counter", 0)
    ctx.engine._ex_counter += 1
    ctx.set_label(str(ctx.engine._ex_counter))
