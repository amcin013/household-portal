"""Themes and font choices.

Each theme is a set of CSS custom properties. They are injected into a <style>
block on every page, so adding a theme here is all it takes to add one to the
picker in Settings -> Appearance. No external font or CSS is loaded - the portal
works on a LAN with no internet.
"""

THEMES = {
    "harbor": {
        "label": "Harbor",
        "hint": "Deep blue-grey, warm brass accents. The default.",
        "mode": "dark",
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
        },
    },
    "gulf": {
        "label": "Gulf",
        "hint": "Bright coastal daylight - sand, sea glass, driftwood.",
        "mode": "light",
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
        },
    },
    "hearth": {
        "label": "Hearth",
        "hint": "Warm paper and wood. Cozy, kitchen-friendly.",
        "mode": "light",
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
        },
    },
    "slate": {
        "label": "Slate",
        "hint": "Neutral dark grey. Quiet and businesslike.",
        "mode": "dark",
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
        },
    },
    "prairie": {
        "label": "Prairie",
        "hint": "Texas green and wheat. Easy on the eyes in daylight.",
        "mode": "light",
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
        },
    },
    "midnight": {
        "label": "Midnight",
        "hint": "Near-black with violet accents. Good on a wall tablet at night.",
        "mode": "dark",
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
        },
    },
    "sepia": {
        "label": "Sepia",
        "hint": "Low-contrast reading tone, like an old cookbook.",
        "mode": "light",
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
        },
    },
    "contrast": {
        "label": "High contrast",
        "hint": "Maximum legibility. Large, plain, high contrast.",
        "mode": "light",
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
        },
    },
}

DEFAULT_THEME = "harbor"

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
