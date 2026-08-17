"""Themes and font choices.

Each theme is a set of CSS custom properties. They are injected into a <style>
block on every page, so adding a theme here is all it takes to add one to the
picker in Settings -> Appearance. No external font or CSS is loaded - the portal
works on a LAN with no internet.

Two families:

  household  - written for this house. Named after places and moods.
  editor     - the well-known code editor schemes, using each project's own
               published palette. Somebody who spends the day in Dracula
               should be able to have the house look like it too.

Every theme defines the same tokens, so nothing in the stylesheet ever has to
ask which theme is on:

  bg / bg-soft      the page behind everything
  surface / -2      cards, and the recessed strips inside them
  border            hairlines - quiet, since cards are separated by shadow
  text / text-dim   body copy, and captions or labels
  accent            one colour: nav pill, chart line, primary button
  accent-contrast   what stays legible *on* the accent
  good/warn/bad     state, deliberately not the accent - "overdue" must read
                    as overdue no matter which theme is on
  t1..t5            the five tile chips on the home page. In the editor themes
                    these are that scheme's syntax colours, which is what makes
                    a Gruvbox house feel like Gruvbox.

A note on text-dim in the editor themes: several schemes use a comment grey
that is fine behind code but too dark for captions on a card (Dracula's
#6272a4). Those are lifted a few steps. Faithful where it works, legible where
it does not - this gets read from across a room on a wall tablet.
"""

THEMES = {
    # ----------------------------------------------------------------- house
    "harbor": {
        "label": "Harbor",
        "hint": "Deep blue-grey, warm brass accents. The default.",
        "mode": "dark",
        "family": "household",
        "vars": {
            "bg": "#0f1720",
            "bg-soft": "#16212c",
            "surface": "#1b2732",
            "surface-2": "#22303d",
            "border": "#2e3f4f",
            "text": "#e8eef4",
            "text-dim": "#9fb0c0",
            "accent": "#e0a458",
            "accent-contrast": "#1a1206",
            "link": "#7fc4e8",
            "good": "#5fbf87",
            "warn": "#e8b04b",
            "bad": "#e0736d",
            "t1": "#e0a458", "t2": "#7fc4e8", "t3": "#5fbf87",
            "t4": "#9d8ede", "t5": "#e0736d",
        },
    },
    "gulf": {
        "label": "Gulf",
        "hint": "Bright coastal daylight - sand, sea glass, driftwood.",
        "mode": "light",
        "family": "household",
        "vars": {
            "bg": "#f4f1ea",
            "bg-soft": "#eae5da",
            "surface": "#ffffff",
            "surface-2": "#f7f4ee",
            "border": "#dcd5c7",
            "text": "#23303a",
            "text-dim": "#5f7180",
            "accent": "#1f7a8c",
            "accent-contrast": "#ffffff",
            "link": "#1f6f8b",
            "good": "#3f8f63",
            "warn": "#b8791f",
            "bad": "#b8453f",
            "t1": "#d9a441", "t2": "#1f7a8c", "t3": "#3f8f63",
            "t4": "#7d74b8", "t5": "#b8453f",
        },
    },
    "hearth": {
        "label": "Hearth",
        "hint": "Warm paper and wood. Cozy, kitchen-friendly.",
        "mode": "light",
        "family": "household",
        "vars": {
            "bg": "#faf6f0",
            "bg-soft": "#f2ebe1",
            "surface": "#ffffff",
            "surface-2": "#f8f2ea",
            "border": "#e3d8c9",
            "text": "#33281f",
            "text-dim": "#7a695a",
            "accent": "#b4552d",
            "accent-contrast": "#ffffff",
            "link": "#9c4a27",
            "good": "#4f7a45",
            "warn": "#b07d23",
            "bad": "#a83c33",
            "t1": "#c98f30", "t2": "#5f86a0", "t3": "#4f7a45",
            "t4": "#98789f", "t5": "#b4552d",
        },
    },
    "slate": {
        "label": "Slate",
        "hint": "Neutral dark grey. Quiet and businesslike.",
        "mode": "dark",
        "family": "household",
        "vars": {
            "bg": "#16181c",
            "bg-soft": "#1c1f24",
            "surface": "#212429",
            "surface-2": "#292d34",
            "border": "#353a42",
            "text": "#e6e8ec",
            "text-dim": "#9aa1ab",
            "accent": "#6ea8fe",
            "accent-contrast": "#0b1220",
            "link": "#8ab6ff",
            "good": "#57bd8a",
            "warn": "#dcae4a",
            "bad": "#e07a75",
            "t1": "#dcae4a", "t2": "#6ea8fe", "t3": "#57bd8a",
            "t4": "#a08ce8", "t5": "#e07a75",
        },
    },
    "prairie": {
        "label": "Prairie",
        "hint": "Texas green and wheat. Easy on the eyes in daylight.",
        "mode": "light",
        "family": "household",
        "vars": {
            "bg": "#f6f7f2",
            "bg-soft": "#ecefe4",
            "surface": "#ffffff",
            "surface-2": "#f4f6ee",
            "border": "#d8ddc9",
            "text": "#242b22",
            "text-dim": "#5f6b58",
            "accent": "#4a7c3f",
            "accent-contrast": "#ffffff",
            "link": "#3f6f4a",
            "good": "#3f7a4a",
            "warn": "#a8791d",
            "bad": "#a8443a",
            "t1": "#a8791d", "t2": "#4a7c8f", "t3": "#4a7c3f",
            "t4": "#7d6fa8", "t5": "#a8443a",
        },
    },
    "midnight": {
        "label": "Midnight",
        "hint": "Near-black with violet accents. Good on a wall tablet at night.",
        "mode": "dark",
        "family": "household",
        "vars": {
            "bg": "#0b0b12",
            "bg-soft": "#12121c",
            "surface": "#171724",
            "surface-2": "#1e1e2e",
            "border": "#2b2b3f",
            "text": "#e7e5f2",
            "text-dim": "#9b98b5",
            "accent": "#a78bfa",
            "accent-contrast": "#140f26",
            "link": "#b9a5ff",
            "good": "#5cc9a0",
            "warn": "#e3b04b",
            "bad": "#f0757f",
            "t1": "#e3b04b", "t2": "#7aa2f7", "t3": "#5cc9a0",
            "t4": "#a78bfa", "t5": "#f0757f",
        },
    },
    "sepia": {
        "label": "Sepia",
        "hint": "Low-contrast reading tone, like an old cookbook.",
        "mode": "light",
        "family": "household",
        "vars": {
            "bg": "#f1e8d9",
            "bg-soft": "#e8ddc9",
            "surface": "#fbf5e9",
            "surface-2": "#f4ecdb",
            "border": "#d9c9ac",
            "text": "#3a2f22",
            "text-dim": "#7d6a51",
            "accent": "#8a6a3b",
            "accent-contrast": "#fdf8ee",
            "link": "#7a5a2b",
            "good": "#5c7a45",
            "warn": "#9c7620",
            "bad": "#9c4433",
            "t1": "#9c7620", "t2": "#5f7d8a", "t3": "#5c7a45",
            "t4": "#8a7a95", "t5": "#9c4433",
        },
    },
    "contrast": {
        "label": "High contrast",
        "hint": "Maximum legibility. Large, plain, high contrast.",
        "mode": "light",
        "family": "household",
        "vars": {
            "bg": "#ffffff",
            "bg-soft": "#f0f0f0",
            "surface": "#ffffff",
            "surface-2": "#f4f4f4",
            "border": "#000000",
            "text": "#000000",
            "text-dim": "#333333",
            "accent": "#00429d",
            "accent-contrast": "#ffffff",
            "link": "#00429d",
            "good": "#106b21",
            "warn": "#8a5a00",
            "bad": "#9c0000",
            "t1": "#7a5000", "t2": "#00429d", "t3": "#106b21",
            "t4": "#5a2d82", "t5": "#9c0000",
        },
    },

    # ---------------------------------------------------------------- editor
    "dracula": {
        "label": "Dracula",
        "hint": "The purple-and-pink classic.",
        "mode": "dark",
        "family": "editor",
        "vars": {
            "bg": "#282a36", "bg-soft": "#2b2d3a",
            "surface": "#2f3240", "surface-2": "#383b4a", "border": "#44475a",
            "text": "#f8f8f2", "text-dim": "#9aa2c0",
            "accent": "#bd93f9", "accent-contrast": "#1a1b23", "link": "#8be9fd",
            "good": "#50fa7b", "warn": "#f1fa8c", "bad": "#ff5555",
            "t1": "#f1fa8c", "t2": "#8be9fd", "t3": "#50fa7b",
            "t4": "#bd93f9", "t5": "#ff79c6",
        },
    },
    "nord": {
        "label": "Nord",
        "hint": "Arctic blue-grey, low saturation.",
        "mode": "dark",
        "family": "editor",
        "vars": {
            "bg": "#2e3440", "bg-soft": "#343b48",
            "surface": "#3b4252", "surface-2": "#434c5e", "border": "#4c566a",
            "text": "#eceff4", "text-dim": "#9aa7bb",
            "accent": "#88c0d0", "accent-contrast": "#16202b", "link": "#81a1c1",
            "good": "#a3be8c", "warn": "#ebcb8b", "bad": "#bf616a",
            "t1": "#ebcb8b", "t2": "#81a1c1", "t3": "#a3be8c",
            "t4": "#b48ead", "t5": "#bf616a",
        },
    },
    "onedark": {
        "label": "One Dark",
        "hint": "Atom's dark default.",
        "mode": "dark",
        "family": "editor",
        "vars": {
            "bg": "#282c34", "bg-soft": "#2c313a",
            "surface": "#31363f", "surface-2": "#3a4049", "border": "#4b5263",
            "text": "#d7dae0", "text-dim": "#8b92a0",
            "accent": "#61afef", "accent-contrast": "#0d1620", "link": "#56b6c2",
            "good": "#98c379", "warn": "#e5c07b", "bad": "#e06c75",
            "t1": "#e5c07b", "t2": "#56b6c2", "t3": "#98c379",
            "t4": "#c678dd", "t5": "#e06c75",
        },
    },
    "monokai": {
        "label": "Monokai",
        "hint": "Sublime's original. Pink, lime, warm charcoal.",
        "mode": "dark",
        "family": "editor",
        "vars": {
            "bg": "#272822", "bg-soft": "#2c2d26",
            "surface": "#31322a", "surface-2": "#3b3c33", "border": "#49483e",
            "text": "#f8f8f2", "text-dim": "#a6a48f",
            "accent": "#f92672", "accent-contrast": "#ffffff", "link": "#66d9ef",
            "good": "#a6e22e", "warn": "#e6db74", "bad": "#ff6188",
            "t1": "#e6db74", "t2": "#66d9ef", "t3": "#a6e22e",
            "t4": "#ae81ff", "t5": "#fd971f",
        },
    },
    "gruvbox": {
        "label": "Gruvbox Dark",
        "hint": "Retro warmth, high contrast.",
        "mode": "dark",
        "family": "editor",
        "vars": {
            "bg": "#282828", "bg-soft": "#2e2b28",
            "surface": "#32302f", "surface-2": "#3c3836", "border": "#504945",
            "text": "#ebdbb2", "text-dim": "#a89984",
            "accent": "#fabd2f", "accent-contrast": "#1d2021", "link": "#83a598",
            "good": "#b8bb26", "warn": "#fe8019", "bad": "#fb4934",
            "t1": "#fabd2f", "t2": "#83a598", "t3": "#b8bb26",
            "t4": "#d3869b", "t5": "#fe8019",
        },
    },
    "tokyonight": {
        "label": "Tokyo Night",
        "hint": "Deep indigo with neon blues.",
        "mode": "dark",
        "family": "editor",
        "vars": {
            "bg": "#1a1b26", "bg-soft": "#1f2030",
            "surface": "#24283b", "surface-2": "#2f334d", "border": "#3b4261",
            "text": "#c0caf5", "text-dim": "#8a94b8",
            "accent": "#7aa2f7", "accent-contrast": "#0b1020", "link": "#7dcfff",
            "good": "#9ece6a", "warn": "#e0af68", "bad": "#f7768e",
            "t1": "#e0af68", "t2": "#7dcfff", "t3": "#9ece6a",
            "t4": "#bb9af7", "t5": "#f7768e",
        },
    },
    "soldark": {
        "label": "Solarized Dark",
        "hint": "Ethan Schoonover's precision palette.",
        "mode": "dark",
        "family": "editor",
        "vars": {
            "bg": "#002b36", "bg-soft": "#04303c",
            "surface": "#073642", "surface-2": "#0d4a58", "border": "#1a5866",
            "text": "#eee8d5", "text-dim": "#93a1a1",
            "accent": "#268bd2", "accent-contrast": "#002b36", "link": "#2aa198",
            "good": "#859900", "warn": "#b58900", "bad": "#dc322f",
            "t1": "#b58900", "t2": "#2aa198", "t3": "#859900",
            "t4": "#6c71c4", "t5": "#d33682",
        },
    },
    "nightowl": {
        "label": "Night Owl",
        "hint": "Sarah Drasner's late-night blue.",
        "mode": "dark",
        "family": "editor",
        "vars": {
            "bg": "#011627", "bg-soft": "#07203a",
            "surface": "#0b2942", "surface-2": "#123b58", "border": "#1d3b53",
            "text": "#d6deeb", "text-dim": "#8badc1",
            "accent": "#82aaff", "accent-contrast": "#00111f", "link": "#7fdbca",
            "good": "#addb67", "warn": "#ecc48d", "bad": "#ef5350",
            "t1": "#ecc48d", "t2": "#7fdbca", "t3": "#addb67",
            "t4": "#c792ea", "t5": "#ef5350",
        },
    },
    "catppuccin": {
        "label": "Catppuccin Mocha",
        "hint": "Soft pastels on deep plum.",
        "mode": "dark",
        "family": "editor",
        "vars": {
            "bg": "#1e1e2e", "bg-soft": "#232336",
            "surface": "#28283c", "surface-2": "#313244", "border": "#45475a",
            "text": "#cdd6f4", "text-dim": "#a6adc8",
            "accent": "#cba6f7", "accent-contrast": "#17172a", "link": "#89b4fa",
            "good": "#a6e3a1", "warn": "#f9e2af", "bad": "#f38ba8",
            "t1": "#f9e2af", "t2": "#89b4fa", "t3": "#a6e3a1",
            "t4": "#cba6f7", "t5": "#f5c2e7",
        },
    },
    "synthwave": {
        "label": "Synthwave '84",
        "hint": "Hot pink on a purple sunset.",
        "mode": "dark",
        "family": "editor",
        "vars": {
            "bg": "#262335", "bg-soft": "#2a273c",
            "surface": "#2d2b41", "surface-2": "#37344e", "border": "#453d64",
            "text": "#f4f4f8", "text-dim": "#b0a7c8",
            "accent": "#ff7edb", "accent-contrast": "#1a0f22", "link": "#36f9f6",
            "good": "#72f1b8", "warn": "#fede5d", "bad": "#fe4450",
            "t1": "#fede5d", "t2": "#36f9f6", "t3": "#72f1b8",
            "t4": "#b893ce", "t5": "#ff7edb",
        },
    },
    "githublight": {
        "label": "GitHub Light",
        "hint": "Clean and neutral. Closest to the reference mock-up.",
        "mode": "light",
        "family": "editor",
        "vars": {
            "bg": "#f6f8fa", "bg-soft": "#eef1f4",
            "surface": "#ffffff", "surface-2": "#f6f8fa", "border": "#d1d9e0",
            "text": "#1f2328", "text-dim": "#59636e",
            "accent": "#0969da", "accent-contrast": "#ffffff", "link": "#0969da",
            "good": "#1a7f37", "warn": "#9a6700", "bad": "#cf222e",
            "t1": "#9a6700", "t2": "#0969da", "t3": "#1a7f37",
            "t4": "#8250df", "t5": "#cf222e",
        },
    },
    "sollight": {
        "label": "Solarized Light",
        "hint": "The warm cream half of Solarized.",
        "mode": "light",
        "family": "editor",
        "vars": {
            "bg": "#fdf6e3", "bg-soft": "#f5eed9",
            "surface": "#fffdf6", "surface-2": "#eee8d5", "border": "#ddd6c1",
            "text": "#073642", "text-dim": "#657b83",
            "accent": "#268bd2", "accent-contrast": "#ffffff", "link": "#2aa198",
            "good": "#859900", "warn": "#b58900", "bad": "#dc322f",
            "t1": "#b58900", "t2": "#2aa198", "t3": "#859900",
            "t4": "#6c71c4", "t5": "#d33682",
        },
    },
    "onelight": {
        "label": "One Light",
        "hint": "Atom's light default. Crisp and airy.",
        "mode": "light",
        "family": "editor",
        "vars": {
            "bg": "#fafafa", "bg-soft": "#f0f0f0",
            "surface": "#ffffff", "surface-2": "#f2f2f2", "border": "#d3d3d3",
            "text": "#383a42", "text-dim": "#696c77",
            "accent": "#4078f2", "accent-contrast": "#ffffff", "link": "#0184bc",
            "good": "#50a14f", "warn": "#c18401", "bad": "#e45649",
            "t1": "#c18401", "t2": "#0184bc", "t3": "#50a14f",
            "t4": "#a626a4", "t5": "#e45649",
        },
    },
    "gruvboxlight": {
        "label": "Gruvbox Light",
        "hint": "Same retro warmth, on cream.",
        "mode": "light",
        "family": "editor",
        "vars": {
            "bg": "#fbf1c7", "bg-soft": "#f2e5bc",
            "surface": "#f9f5d7", "surface-2": "#f2e5bc", "border": "#d5c4a1",
            "text": "#3c3836", "text-dim": "#7c6f64",
            "accent": "#af3a03", "accent-contrast": "#fbf1c7", "link": "#076678",
            "good": "#79740e", "warn": "#b57614", "bad": "#9d0006",
            "t1": "#b57614", "t2": "#076678", "t3": "#79740e",
            "t4": "#8f3f71", "t5": "#9d0006",
        },
    },
    "rosepine": {
        "label": "Rosé Pine Dawn",
        "hint": "Muted rose and pine on warm white.",
        "mode": "light",
        "family": "editor",
        "vars": {
            "bg": "#faf4ed", "bg-soft": "#f2e9e1",
            "surface": "#fffaf3", "surface-2": "#f2e9e1", "border": "#dfdad9",
            "text": "#575279", "text-dim": "#797593",
            "accent": "#907aa9", "accent-contrast": "#ffffff", "link": "#286983",
            "good": "#286983", "warn": "#ea9d34", "bad": "#b4637a",
            "t1": "#ea9d34", "t2": "#56949f", "t3": "#286983",
            "t4": "#907aa9", "t5": "#b4637a",
        },
    },
}

DEFAULT_THEME = "harbor"

# Shown as headings in the picker, in this order.
FAMILIES = [
    ("household", "For the house",
     "Written for this place - named after where you live and how it feels."),
    ("editor", "Editor schemes",
     "The palettes from well-known code editors, using each project's own colours."),
]


def themes_by_family():
    """The picker groups 23 themes; an ungrouped grid of that many is a wall."""
    return [
        (key, label, blurb,
         {k: v for k, v in THEMES.items() if v.get("family", "household") == key})
        for key, label, blurb in FAMILIES
    ]


# Only fonts that ship with common systems, so nothing has to be downloaded.
FONTS = {
    "system": {
        "label": "System",
        "stack": ("-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
                  "'Helvetica Neue', Arial, 'Liberation Sans', 'DejaVu Sans', "
                  "sans-serif"),
    },
    "humanist": {
        "label": "Humanist",
        "stack": "'Segoe UI', Candara, 'Trebuchet MS', Verdana, 'DejaVu Sans', sans-serif",
    },
    "grotesque": {
        "label": "Grotesque",
        "stack": "'Helvetica Neue', Helvetica, Arial, 'Liberation Sans', 'DejaVu Sans', sans-serif",
    },
    "rounded": {
        "label": "Rounded",
        "stack": ("ui-rounded, 'SF Pro Rounded', 'Nunito', 'Trebuchet MS', "
                  "Verdana, sans-serif"),
    },
    "serif": {
        "label": "Serif",
        "stack": "Georgia, 'Iowan Old Style', 'Times New Roman', 'Liberation Serif', serif",
    },
    "bookish": {
        "label": "Bookish",
        "stack": "'Palatino Linotype', Palatino, 'Book Antiqua', Georgia, serif",
    },
    "slab": {
        "label": "Slab",
        "stack": "Rockwell, 'Roboto Slab', 'Courier New', Georgia, serif",
    },
    "mono": {
        "label": "Monospace",
        "stack": "ui-monospace, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace",
    },
}

DEFAULT_FONT = "system"

DENSITIES = {
    "comfortable": {"label": "Comfortable", "scale": "1"},
    "compact": {"label": "Compact", "scale": "0.9"},
    "large": {"label": "Large print", "scale": "1.15"},
}

DEFAULT_DENSITY = "comfortable"


def theme_css(theme_key, font_key, density_key):
    """Build the :root custom-property block for the chosen combination."""
    theme = THEMES.get(theme_key) or THEMES[DEFAULT_THEME]
    font = FONTS.get(font_key) or FONTS[DEFAULT_FONT]
    density = DENSITIES.get(density_key) or DENSITIES[DEFAULT_DENSITY]

    lines = [f"  --{name}: {value};" for name, value in theme["vars"].items()]
    lines.append(f"  --font-body: {font['stack']};")
    lines.append(f"  --scale: {density['scale']};")
    return ":root {\n" + "\n".join(lines) + "\n}"


def theme_mode(theme_key):
    return (THEMES.get(theme_key) or THEMES[DEFAULT_THEME])["mode"]
