"""The starter cookbook.

These recipes exist to make the cookbook look like a cookbook, so the test is
mostly about the shape of the data the templates rely on: section headings,
quantity-less lines, a spread of courses and tags. If somebody trims the set
later, this says what it was for.
"""
import pytest

from portal.seed_recipes import RECIPES


def test_every_recipe_has_what_the_card_needs():
    for spec in RECIPES:
        assert spec["title"]
        assert spec["description"]
        assert spec["servings"] > 0
        assert spec["serving_noun"]
        assert spec["course"]
        assert spec["instructions"].strip()


def test_titles_are_unique():
    titles = [r["title"] for r in RECIPES]
    assert len(titles) == len(set(titles))


def test_the_set_spreads_across_courses():
    """One course means the course filter has nothing to do."""
    assert len({r["course"] for r in RECIPES}) >= 5


def test_tags_overlap_so_the_chips_group():
    tags = [t.strip() for r in RECIPES for t in r["tags"].split(",")]
    shared = {t for t in tags if tags.count(t) > 1}
    assert len(shared) >= 5


def test_some_recipes_use_ingredient_headings():
    assert any(any(row[4] for row in r["ingredients"]) for r in RECIPES)


def test_some_ingredients_have_no_quantity():
    """"Salt to taste" must survive the scaler, which multiplies quantities."""
    assert any(
        any(row[0] is None and not row[4] for row in r["ingredients"])
        for r in RECIPES
    )


def test_at_least_one_favourite_so_the_kitchen_panel_fills():
    assert any(r.get("favorite") for r in RECIPES)


@pytest.mark.parametrize("spec", RECIPES, ids=lambda s: s["title"])
def test_ingredient_rows_are_well_formed(spec):
    for row in spec["ingredients"]:
        qty, unit, item, note, heading = row
        assert item, f"{spec['title']}: ingredient with no name"
        if heading:
            assert qty is None and unit is None
        if qty is not None:
            assert qty > 0, f"{spec['title']}: {item} has quantity {qty}"


def test_seeding_creates_them_and_is_safe_to_repeat(app):
    from portal.models import Recipe, RecipeIngredient
    from portal.seed import run_seed

    with app.app_context():
        run_seed()
        first = Recipe.query.count()
        lines = RecipeIngredient.query.count()
        assert first >= len(RECIPES)
        assert lines > 0

        run_seed()
        assert Recipe.query.count() == first
        assert RecipeIngredient.query.count() == lines
