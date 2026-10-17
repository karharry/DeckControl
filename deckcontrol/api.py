"""Public plugin API.  A plugin is any .py file dropped in DeckControl-data/plugins/.

    from deckcontrol.api import action, Param

    @action("shout", "Shout text", category="My stuff",
            params=[Param("text", "Text", default="hello")])
    def shout(ctx, p):
        print(p["text"].upper())

ctx gives you: ctx.engine, ctx.control ("k1", "e2" ...), ctx.event ("press",
"release", "long", "cw", "ccw"), ctx.deck_brightness(n), ctx.goto_page(name),
ctx.set_label(text), ctx.log(msg).
"""
from dataclasses import dataclass, field

REGISTRY = {}


@dataclass
class Param:
    name: str
    label: str = ""
    type: str = "text"          # text | textarea | number | bool | select | keys | path
    default: object = ""
    options: list = field(default_factory=list)   # for select
    help: str = ""

    def to_json(self):
        return {"name": self.name, "label": self.label or self.name, "type": self.type,
                "default": self.default, "options": self.options, "help": self.help}


def action(id, label, category="Custom", params=None, desc="", icon="⚙"):
    def deco(fn):
        REGISTRY[id] = {"id": id, "label": label, "category": category,
                        "params": params or [], "desc": desc, "icon": icon, "fn": fn}
        return fn
    return deco


def describe():
    out = []
    for a in REGISTRY.values():
        out.append({"id": a["id"], "label": a["label"], "category": a["category"],
                    "desc": a["desc"], "icon": a["icon"],
                    "params": [p.to_json() for p in a["params"]]})
    return out
