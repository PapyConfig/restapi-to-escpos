"""Built-in memo templates: fields, value validation and layout (values → print commands).

Single source of truth for the API (`/v1/templates`) and the web UI. Layouts adapt to the
number of columns of the target printer and only use characters the printer can print.
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi.exceptions import RequestValidationError
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError, create_model

from .config import PrinterConfig
from .models import PrintJob, TemplateField, TemplateInfo, TemplateOption, TemplateRequest

Values = dict[str, Any]
Commands = list[dict[str, Any]]


@dataclass(frozen=True)
class Context:
    columns: int  # characters per line, font A, width 1
    columns_b: int  # characters per line, font B, width 1
    now: datetime
    seed: int


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    glyph: str
    description: str
    fields: list[TemplateField]
    build: Callable[[Values, Context], Commands]

    def info(self) -> TemplateInfo:
        return TemplateInfo(
            id=self.id,
            name=self.name,
            glyph=self.glyph,
            description=self.description,
            fields=self.fields,
        )


# -- layout helpers ----------------------------------------------------------------------


def txt(content: str, **style: Any) -> dict[str, Any]:
    return {
        "type": "text",
        "content": content if content.endswith("\n") else f"{content}\n",
        **style,
    }


def feed(lines: int = 1) -> dict[str, Any]:
    return {"type": "feed", "lines": lines}


def sep(char: str = "-") -> dict[str, Any]:
    return {"type": "separator", "char": char}


def wrap_words(text: str, width: int) -> list[str]:
    """Word-wrap each paragraph to `width` characters, cutting words longer than a line."""
    out: list[str] = []
    for paragraph in str(text).split("\n"):
        line = ""
        for word in paragraph.split():
            while len(word) > width:
                if line:
                    out.append(line)
                    line = ""
                out.append(word[:width])
                word = word[width:]
            if not line:
                line = word
            elif len(line) + 1 + len(word) <= width:
                line += f" {word}"
            else:
                out.append(line)
                line = word
        out.append(line)
    return out


def wrapped(text: str, width: int) -> str:
    return "\n".join(wrap_words(text, width))


def hanging(prefix: str, text: str, columns: int) -> str:
    """Wrap with a hanging indent: continuation lines align after `prefix`."""
    pad = " " * len(prefix)
    lines = wrap_words(text, columns - len(prefix))
    return "\n".join((pad if i else prefix) + line for i, line in enumerate(lines))


def center_pad(text: str, width: int) -> str:
    text = text[:width]
    left = (width - len(text)) // 2
    return " " * left + text + " " * (width - len(text) - left)


def band(label: str, columns: int, size: int = 1) -> dict[str, Any]:
    """Full-width inverted band with a centered label."""
    width = columns // size
    return txt(center_pad(label, width), invert=True, bold=True, width=size, height=size)


def two_sides(left: str, right: str, width: int) -> str:
    return left + " " * max(1, width - len(left) - len(right)) + right


def label_value(label: str, value: str, columns: int) -> str:
    """`label ... value` on one line, or the label then the value cut to the line width."""
    if len(label) + 1 + len(value) <= columns:
        return two_sides(label, value, columns)
    chunks = [value[i : i + columns] for i in range(0, len(value), columns)] or [""]
    return "\n".join([label, *chunks])


def non_empty_lines(text: str) -> list[str]:
    return [stripped for line in str(text).split("\n") if (stripped := line.strip())]


WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


def long_date(d: date) -> str:
    """'Mercredi 25 novembre 2026' (French, independent of the system locale)."""
    return f"{WEEKDAYS[d.weekday()].capitalize()} {d.day} {MONTHS[d.month - 1]} {d.year}"


def parse_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def hour(value: str) -> str:
    return value.replace(":", "h")


def stamp(ctx: Context) -> dict[str, Any]:
    return txt(f"{long_date(ctx.now)}, {ctx.now:%Hh%M}", font="b", align="right")


QUOTES: list[tuple[str, str]] = [
    ("Il faut cultiver notre jardin.", "Voltaire"),
    ("Rien ne sert de courir ; il faut partir à point.", "Jean de La Fontaine"),
    ("Patience et longueur de temps font plus que force ni que rage.", "Jean de La Fontaine"),
    ("Le cœur a ses raisons que la raison ne connaît point.", "Blaise Pascal"),
    ("Que sais-je ?", "Michel de Montaigne"),
    ("Je pense, donc je suis.", "René Descartes"),
    ("Ceux qui vivent, ce sont ceux qui luttent.", "Victor Hugo"),
    ("Ce que l'on conçoit bien s'énonce clairement.", "Nicolas Boileau"),
    ("Hâtez-vous lentement, et sans perdre courage.", "Nicolas Boileau"),
    ("Le travail éloigne de nous trois grands maux : l'ennui, le vice et le besoin.", "Voltaire"),
    (
        "Le temps est un grand maître, dit-on. Le malheur est qu'il tue ses élèves.",
        "Hector Berlioz",
    ),
]

MOODS = {
    "rayonnant": "(^o^)  Rayonnant",
    "bien": "(^_^)  Bien",
    "moyen": "(-_-)  Bof",
    "fatigue": "(=_=)  Fatigué",
    "orageux": "(>_<)  Orageux",
}


def wifi_escape(value: str) -> str:
    return re.sub(r'([\\;,:"])', r"\\\1", value)


def code128_dots(content: str, module_width: int) -> int:
    """Approximate printed width of a CODE128 (set B) barcode, quiet zones excluded."""
    return (11 * (len(content) + 3) + 2) * module_width


# -- field shorthands --------------------------------------------------------------------


def _field(key: str, label: str, type_: str = "text", **kwargs: Any) -> TemplateField:
    return TemplateField(key=key, label=label, type=type_, **kwargs)


def _options(*pairs: tuple[str, str]) -> list[TemplateOption]:
    return [TemplateOption(value=v, label=label) for v, label in pairs]


# -- templates ---------------------------------------------------------------------------


def _memo(v: Values, ctx: Context) -> Commands:
    c = ctx.columns
    out = [band("MÉMO", c, 2), feed()]
    if v["titre"]:
        out += [txt(wrapped(v["titre"], c // 2), bold=True, width=2, height=2), feed()]
    if v["message"]:
        out.append(txt(wrapped(v["message"], c)))
    if v["signature"]:
        out += [feed(), txt(wrapped(f"- {v['signature']}", c), align="right")]
    if v["date"]:
        out += [sep(), stamp(ctx)]
    return out


def _todo(v: Values, ctx: Context) -> Commands:
    c = ctx.columns
    out: Commands = []
    if v["priorite"] == "haute":
        out += [band("! URGENT !", c, 2), feed()]
    out.append(txt(wrapped(v["titre"] or "À faire", c // 2), bold=True, width=2, height=2))
    if due := parse_date(v["echeance"]):
        out.append(txt(wrapped(f"Pour le {long_date(due).lower()}", c), underline=1))
    out.append(sep("═"))
    tasks = non_empty_lines(v["taches"])
    for task in tasks:
        out += [txt(hanging("[ ] ", task, c)), feed()]
    count = f"{len(tasks)} tâche{'s' if len(tasks) > 1 else ''}"
    out += [sep("═"), txt(two_sides(count, f"Priorité {v['priorite']}", c)), stamp(ctx)]
    return out


def _shopping(v: Values, ctx: Context) -> Commands:
    c = ctx.columns
    items = non_empty_lines(v["articles"])
    out = [txt("COURSES", bold=True, width=3, height=3, align="center")]
    if v["magasin"]:
        out.append(txt(wrapped(v["magasin"], ctx.columns_b), align="center", font="b"))
    out.append(sep("─"))
    half = c // 2
    if len(items) > 4 and all(len(i) <= half - 5 for i in items):
        rows = (len(items) + 1) // 2
        lines = []
        for r in range(rows):
            left = f"[ ] {items[r]}".ljust(half)
            right = f"[ ] {items[r + rows]}" if r + rows < len(items) else ""
            lines.append((left + right).rstrip())
        out.append(txt("\n\n".join(lines)))
    else:
        out.append(txt("\n\n".join(hanging("[ ] ", i, c) for i in items)))
    plural = "s" if len(items) > 1 else ""
    out += [sep("─"), txt(f"{len(items)} article{plural}", align="right", font="b")]
    return out


def _postit(v: Values, ctx: Context) -> Commands:
    size = int(v["taille"])
    width = max(1, ctx.columns // size)
    lines = wrap_words(v["texte"], width)
    if v["inverse"]:
        lines = [center_pad(line, width) for line in lines]
    style = {"bold": True, "width": size, "height": size, "align": "center"}
    return [feed(), txt("\n".join(lines), **style, invert=v["inverse"]), feed()]


def _note(v: Values, ctx: Context) -> Commands:
    c = ctx.columns
    inner = c - 4
    body: list[str] = []
    if v["pour"]:
        body += [*wrap_words(f"Pour {v['pour']},", inner), ""]
    body += wrap_words(v["message"], inner)
    if v["de"]:
        body += ["", *(line.rjust(inner) for line in wrap_words(v["de"], inner))]
    rows = [f"║ {line.ljust(inner)} ║" for line in ["", *body, ""]]
    return [txt("\n".join([f"╔{'═' * (c - 2)}╗", *rows, f"╚{'═' * (c - 2)}╝"]))]


def _reminder(v: Values, ctx: Context) -> Commands:
    c = ctx.columns
    out = [
        band("RAPPEL", c, 2),
        feed(),
        txt(wrapped(v["quoi"], c // 2), bold=True, width=2, height=2, align="center"),
    ]
    if day := parse_date(v["quand"]):
        when = long_date(day) + (f" à {hour(v['heure'])}" if v["heure"] else "")
        out.append(txt(wrapped(when, c), align="center", underline=1))
    if v["note"]:
        out += [feed(), txt(wrapped(v["note"], c))]
    if v["lien"]:
        out += [
            feed(),
            {"type": "qr", "content": v["lien"], "size": 6, "ec": "M", "align": "center"},
            txt("Scanne pour ouvrir", align="center", font="b"),
        ]
    return out


def _wifi(v: Values, ctx: Context) -> Commands:
    c = ctx.columns
    security = v["security"]
    password = "" if security == "nopass" else f"P:{wifi_escape(v['password'])};"
    hidden = "H:true;" if v["hidden"] else ""
    qr = f"WIFI:T:{security};S:{wifi_escape(v['ssid'])};{password}{hidden};"
    out = [
        txt("Bienvenue !", bold=True, width=2, height=2, align="center"),
        txt(wrapped("Scanne pour te connecter au Wi-Fi", c), align="center"),
        feed(),
        {"type": "qr", "content": qr, "size": 8, "ec": "M", "align": "center"},
        feed(),
        sep("─"),
        txt(label_value("Réseau", v["ssid"], c)),
    ]
    if security != "nopass":
        out.append(txt(label_value("Mot de passe", v["password"], c), bold=True))
    return out


def _kanban(v: Values, ctx: Context) -> Commands:
    c = ctx.columns
    project = f" {(v['projet'] or 'tâche').upper()} "
    out = [txt(two_sides(project, f" {v['taille']} ", c), invert=True, bold=True), feed()]
    out += [txt(wrapped(v["titre"], c // 2), bold=True, width=2, height=2), feed()]
    if card_id := v["id"]:
        if card_id.isascii() and code128_dots(card_id, 2) <= c * 12:
            out.append(
                {
                    "type": "barcode",
                    "content": card_id,
                    "symbology": "CODE128",
                    "height": 60,
                    "module_width": 2,
                    "text_position": "below",
                    "align": "center",
                }
            )
        else:  # too wide for the paper (or not encodable): print the id as text
            out.append(txt(wrapped(card_id, c // 2), bold=True, width=2, align="center"))
    out.append(txt(f"Créée le {ctx.now:%d/%m/%Y}", font="b", align="right"))
    return out


def _journal(v: Values, ctx: Context) -> Commands:
    c = ctx.columns
    day = parse_date(v["jour"]) or ctx.now.date()
    out = [
        txt("Journal", bold=True, width=2, height=2, align="center"),
        txt(long_date(day), align="center"),
        sep("·"),
    ]
    if wins := non_empty_lines(v["victoires"])[:5]:
        out.append(txt("Victoires du jour", bold=True, underline=1))
        out += [txt(hanging(f"{i}. ", win, c)) for i, win in enumerate(wins, 1)]
        out.append(feed())
    if v["merci"]:
        out += [txt("Merci pour", bold=True, underline=1), txt(wrapped(v["merci"], c)), feed()]
    out.append(txt(MOODS[v["humeur"]], align="center", width=2))
    return out


def _quote(v: Values, ctx: Context) -> Commands:
    c = ctx.columns
    quote, author = v["citation"].strip(), v["auteur"]
    if not quote:
        quote, author = QUOTES[ctx.seed % len(QUOTES)]
    out = [
        txt("«", width=3, height=3, bold=True),
        txt("\n".join(f"  {line}" for line in wrap_words(quote, c - 4)), bold=True),
        txt("»", width=3, height=3, bold=True, align="right"),
    ]
    if author:
        out.append(txt(wrapped(f"- {author}", c), align="right"))
    out += [sep("·"), txt(long_date(ctx.now), font="b", align="center")]
    return out


TEMPLATES: list[Template] = [
    Template(
        "memo",
        "Mémo",
        "▀▀",
        "Un titre, un message, la date. Le classique.",
        [
            _field("titre", "Titre", max=60, placeholder="Appeler le plombier"),
            _field(
                "message",
                "Message",
                "textarea",
                required=True,
                max=2000,
                placeholder="Avant jeudi, pour la fuite sous l'évier.",
            ),
            _field("signature", "Signé", max=40),
            _field("date", "Ajouter la date", "checkbox", default=True),
        ],
        _memo,
    ),
    Template(
        "todo",
        "À faire",
        "[ ]",
        "Une liste de tâches à cocher au stylo.",
        [
            _field("titre", "Titre", default="À faire", max=40),
            _field(
                "taches",
                "Tâches (une par ligne)",
                "textarea",
                required=True,
                max=3000,
                placeholder="Sortir les poubelles\nRépondre à Paul\nRéserver le train",
            ),
            _field("echeance", "Échéance", "date"),
            _field(
                "priorite",
                "Priorité",
                "select",
                default="normale",
                options=_options(("basse", "Basse"), ("normale", "Normale"), ("haute", "Haute")),
            ),
        ],
        _todo,
    ),
    Template(
        "shopping",
        "Courses",
        "▒▒",
        "La liste à emporter. Deux colonnes si les articles sont courts.",
        [
            _field(
                "articles",
                "Articles (un par ligne)",
                "textarea",
                required=True,
                max=3000,
                placeholder="Lait\nPain\nTomates\nCafé",
            ),
            _field("magasin", "Magasin", max=40),
        ],
        _shopping,
    ),
    Template(
        "postit",
        "Pense-bête XXL",
        "██",
        "Trois mots en énorme, à coller sur le frigo ou l'écran.",
        [
            _field("texte", "Texte", required=True, max=40, placeholder="CLÉS !"),
            _field(
                "taille",
                "Taille",
                "select",
                default="4",
                options=_options(("3", "Grand"), ("4", "Très grand"), ("6", "Énorme")),
            ),
            _field("inverse", "Blanc sur noir", "checkbox", default=False),
        ],
        _postit,
    ),
    Template(
        "note",
        "Petit mot",
        "╔╗",
        "Pour quelqu'un, dans un cadre. À glisser sous une porte.",
        [
            _field("pour", "Pour", max=30, placeholder="Camille"),
            _field(
                "message",
                "Message",
                "textarea",
                required=True,
                max=1000,
                placeholder="Il reste des lasagnes dans le frigo.",
            ),
            _field("de", "De", max=30),
        ],
        _note,
    ),
    Template(
        "reminder",
        "Rappel + lien",
        "▄▀",
        "Quoi, quand, et un QR code pour ouvrir le lien.",
        [
            _field("quoi", "Quoi", required=True, max=60, placeholder="Renouveler le passeport"),
            _field("quand", "Date", "date", auto="today"),
            _field("heure", "Heure", "time"),
            _field("lien", "Lien (QR code)", max=500, placeholder="https://…"),
            _field("note", "Détails", "textarea", max=1000),
        ],
        _reminder,
    ),
    Template(
        "wifi",
        "Wi-Fi invités",
        "((·))",
        "Le QR code qui connecte les invités sans rien taper.",
        [
            _field("ssid", "Nom du réseau", required=True, max=32),
            _field("password", "Mot de passe", max=63),
            _field(
                "security",
                "Sécurité",
                "select",
                default="WPA",
                options=_options(("WPA", "WPA/WPA2/WPA3"), ("WEP", "WEP"), ("nopass", "Aucune")),
            ),
            _field("hidden", "Réseau masqué", "checkbox", default=False),
        ],
        _wifi,
    ),
    Template(
        "kanban",
        "Carte tâche",
        "|||",
        "Une carte de tableau Kanban, avec un code-barres d'identifiant.",
        [
            _field("titre", "Tâche", required=True, max=80, placeholder="Migrer Traefik en v3"),
            _field("projet", "Projet", max=24, placeholder="homelab"),
            _field(
                "taille",
                "Estimation",
                "select",
                default="M",
                options=_options(*((s, s) for s in ("XS", "S", "M", "L", "XL"))),
            ),
            _field("id", "Identifiant", max=20, auto="id"),
        ],
        _kanban,
    ),
    Template(
        "journal",
        "Journal du jour",
        "≡",
        "Trois victoires, un merci, une humeur. Pour finir la journée.",
        [
            _field("jour", "Jour", "date", auto="today"),
            _field(
                "victoires",
                "Trois victoires (une par ligne)",
                "textarea",
                max=1000,
                placeholder="Fini le rapport\nCouru 5 km\nAppelé mamie",
            ),
            _field("merci", "Merci pour…", max=120),
            _field(
                "humeur",
                "Humeur",
                "select",
                default="bien",
                options=_options(
                    ("rayonnant", "Rayonnant"),
                    ("bien", "Bien"),
                    ("moyen", "Bof"),
                    ("fatigue", "Fatigué"),
                    ("orageux", "Orageux"),
                ),
            ),
        ],
        _journal,
    ),
    Template(
        "quote",
        "Pensée du jour",
        "« »",
        "Une citation tirée au hasard, ou la tienne.",
        [
            _field("citation", "Citation (vide = au hasard)", "textarea", max=500),
            _field("auteur", "Auteur", max=60),
        ],
        _quote,
    ),
]

TEMPLATES_BY_ID: dict[str, Template] = {t.id: t for t in TEMPLATES}


# -- values ------------------------------------------------------------------------------


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty")
    return value


def _valid_date(value: str) -> str:
    if value:
        date.fromisoformat(value)  # ValueError on 2026-02-31
    return value


def _annotation(f: TemplateField, partial: bool) -> tuple[Any, Any]:
    """Pydantic (type, default) for a field. `partial`: required fields may be empty."""
    if f.type == "checkbox":
        return bool, f.default if f.default is not None else False
    if f.type == "select":
        choices = tuple(o.value for o in f.options or [])
        return Literal[choices], f.default if f.default is not None else choices[0]
    checks: list[Any] = []
    if f.type == "date":
        checks += [Field(pattern=r"^(\d{4}-\d{2}-\d{2})?$"), AfterValidator(_valid_date)]
    elif f.type == "time":
        checks.append(Field(pattern=r"^(([01]\d|2[0-3]):[0-5]\d)?$"))
    else:
        checks.append(Field(max_length=f.max))
    if f.required and not partial:
        checks.append(AfterValidator(_not_blank))
        return Annotated[str, *checks], ...
    return Annotated[str, *checks], f.default if f.default is not None else ""


def _values_model(template: Template, partial: bool) -> type[BaseModel]:
    fields = {f.key: _annotation(f, partial) for f in template.fields}
    config = ConfigDict(extra="forbid", strict=True)
    name = f"{template.id.capitalize()}{'Draft' if partial else ''}Values"
    return create_model(name, __config__=config, **fields)


_VALUE_MODELS = {
    (t.id, partial): _values_model(t, partial) for t in TEMPLATES for partial in (False, True)
}


def auto_value(f: TemplateField, now: datetime) -> str:
    match f.auto:
        case "today":
            return f"{now:%Y-%m-%d}"
        case "now":
            return f"{now:%H:%M}"
        case "id":
            return f"T-{now:%m%d}-{now:%H%M}"
    return ""


def validate_values(
    template: Template, values: dict[str, object], now: datetime, partial: bool = False
) -> Values:
    """Apply automatic values to omitted keys, then validate. Errors point at `values.<key>`."""
    given = {f.key: auto_value(f, now) for f in template.fields if f.auto and f.key not in values}
    given.update(values)
    try:
        return _VALUE_MODELS[template.id, partial].model_validate(given).model_dump()
    except ValidationError as exc:
        errors = [{**e, "loc": ("body", "values", *e["loc"])} for e in exc.errors()]
        raise RequestValidationError(errors) from None


def render_template(
    template: Template, request: TemplateRequest, printer: PrinterConfig, partial: bool = False
) -> PrintJob:
    """Build the print job of a template for a printer. Deterministic for a given now/seed.

    `partial` (preview while typing): required fields may be omitted or empty.
    """
    now = request.now or datetime.now().astimezone()
    seed = request.seed if request.seed is not None else secrets.randbelow(1_000_000)
    values = validate_values(template, request.values, now, partial)
    ctx = Context(printer.columns("a"), printer.columns("b"), now, seed)
    commands = template.build(values, ctx)
    return PrintJob(printer=printer.name, cut=request.cut, commands=commands)
