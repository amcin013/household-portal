"""Theme and font plumbing.

These exist because the font picker was broken twice over for months without
anything failing: the stacks named fonts that were not installed, and the
injected <style> block was HTML-escaped so the quoted family names were
invalid CSS. Neither showed up as an error - the page just rendered in the
wrong face. Both are cheap to assert and expensive to notice by eye.
"""
import pathlib
import re

import pytest

from portal.themes import (
    DEFAULT_FONT, DEFAULT_THEME, FONTS, LEGACY_FONTS, THEMES,
    resolve_font, theme_css, themes_by_family,
)

FONT_DIR = pathlib.Path(__file__).resolve().parent.parent / "portal" / "static" / "fonts"


def test_every_theme_defines_the_same_tokens():
    """A theme missing a token emits a broken var() that only shows on that theme."""
    expected = set(THEMES[DEFAULT_THEME]["vars"])
    for key, theme in THEMES.items():
        assert set(theme["vars"]) == expected, f"{key} token set differs"


def test_every_theme_has_the_five_tile_tints():
    for key, theme in THEMES.items():
        for tint in ("t1", "t2", "t3", "t4", "t5"):
            assert theme["vars"].get(tint), f"{key} has no {tint}"


def test_theme_colours_are_valid_hex():
    for key, theme in THEMES.items():
        for name, value in theme["vars"].items():
            assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), f"{key}.{name} = {value!r}"


def test_every_theme_declares_a_mode_and_family():
    for key, theme in THEMES.items():
        assert theme["mode"] in ("light", "dark"), key
        assert theme.get("family") in ("household", "editor"), key


def test_families_account_for_every_theme():
    grouped = sum(len(group) for _, _, _, group in themes_by_family())
    assert grouped == len(THEMES)


def test_font_files_are_present_for_every_shipped_font():
    """The stack names a family; if the woff2 is missing the browser gets nothing."""
    for key, font in FONTS.items():
        if key == "system":
            continue
        assert (FONT_DIR / f"{key}.woff2").is_file(), f"no woff2 for {key}"


def test_css_declares_a_face_for_every_shipped_font():
    css = (FONT_DIR.parent / "css" / "app.css").read_text()
    for key, font in FONTS.items():
        if key == "system":
            continue
        assert f"{key}.woff2" in css, f"{key} has no @font-face"


@pytest.mark.parametrize("legacy,expected", sorted(LEGACY_FONTS.items()))
def test_legacy_font_keys_still_resolve(legacy, expected):
    assert resolve_font(legacy) is FONTS[expected]


def test_unknown_font_falls_back_rather_than_raising():
    assert resolve_font("no-such-font") is FONTS[DEFAULT_FONT]


def test_theme_style_is_not_html_escaped(auth_client):
    """The regression that broke every font: &#39; is not valid CSS."""
    page = auth_client.get("/", follow_redirects=True).get_data(as_text=True)
    style = re.search(r"<style>(.*?)</style>", page, re.S).group(1)
    assert "&#39;" not in style
    assert "&amp;" not in style
    assert "&quot;" not in style


def test_font_family_reaches_the_page_with_real_quotes(auth_client):
    page = auth_client.get("/", follow_redirects=True).get_data(as_text=True)
    declared = re.search(r"--font-body: ([^;]+);", page).group(1)
    assert "'" in declared or declared.startswith("system-ui")


def test_theme_css_emits_every_token():
    css = theme_css(DEFAULT_THEME, DEFAULT_FONT, "comfortable")
    for name in THEMES[DEFAULT_THEME]["vars"]:
        assert f"--{name}:" in css
    assert "--font-body:" in css
    assert "--scale:" in css
