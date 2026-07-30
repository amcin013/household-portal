"""Scaling and nutrition - the parts where a wrong number is worst."""
import pytest

from portal.extensions import db
from portal.models import Food, Recipe, RecipeIngredient
from portal.services.nutrition import (
    grams_for, nutrition_for, scale_ingredients, shopping_list,
)


@pytest.fixture
def chili(app):
    beef = Food(name="Ground beef", kcal=254, protein_g=17.2, carbs_g=0, fat_g=20)
    onion = Food(name="Onion", kcal=40, protein_g=1.1, carbs_g=9.3, fat_g=0.1)
    onion.unit_grams = {"cup": 160, "each": 110}
    db.session.add_all([beef, onion])
    db.session.flush()

    recipe = Recipe(title="Chili", slug="chili", servings=4)
    recipe.ingredients = [
        RecipeIngredient(position=0, item="For the pot", heading=True),
        RecipeIngredient(position=1, quantity=1.5, unit="lb", item="Ground beef",
                         food_id=beef.id),
        RecipeIngredient(position=2, quantity=2, unit="cup", item="Onion",
                         food_id=onion.id),
        RecipeIngredient(position=3, quantity=None, item="Salt"),
    ]
    db.session.add(recipe)
    db.session.commit()
    return recipe


def test_scaling_doubles_quantities(chili):
    rows, factor = scale_ingredients(chili, 8)
    assert factor == 2
    beef = next(r for r in rows if r["item"] == "Ground beef")
    assert beef["quantity"] == 3.0


def test_scaling_halves_quantities(chili):
    rows, factor = scale_ingredients(chili, 2)
    assert factor == 0.5
    beef = next(r for r in rows if r["item"] == "Ground beef")
    assert beef["quantity"] == 0.75


def test_scaling_leaves_to_taste_alone(chili):
    """'Salt to taste' has no quantity and must not become 0."""
    rows, _ = scale_ingredients(chili, 40)
    salt = next(r for r in rows if r["item"] == "Salt")
    assert salt["quantity"] is None


def test_headings_are_not_scaled_or_counted(chili):
    rows, _ = scale_ingredients(chili, 8)
    heading = next(r for r in rows if r["heading"])
    assert heading["quantity"] is None

    result = nutrition_for(chili, 8)
    assert "For the pot" not in result["counted"]
    assert "For the pot" not in result["uncounted"]


def test_grams_from_standard_units(chili):
    beef = chili.ingredients[1]
    assert grams_for(beef, 1.5) == pytest.approx(680.39, rel=1e-3)


def test_grams_from_food_specific_units(chili):
    """A cup of onion is 160 g, not the generic 240 ml default."""
    onion = chili.ingredients[2]
    assert grams_for(onion, 2) == 320


def test_nutrition_per_serving(chili):
    result = nutrition_for(chili, 4)
    # 680.39g beef @254/100g = 1728.2 ; 320g onion @40/100g = 128
    assert result["totals"]["kcal"] == pytest.approx(1856.2, rel=1e-3)
    assert result["per_serving"]["kcal"] == pytest.approx(464.05, rel=1e-3)


def test_nutrition_scales_with_servings(chili):
    """Per-serving calories stay the same however many servings you make."""
    four = nutrition_for(chili, 4)["per_serving"]["kcal"]
    twelve = nutrition_for(chili, 12)["per_serving"]["kcal"]
    assert four == pytest.approx(twelve)


def test_uncounted_ingredients_are_reported(chili):
    result = nutrition_for(chili, 4)
    assert "Salt" in result["uncounted"]
    assert result["coverage"] == pytest.approx(2 / 3)


def test_recipe_with_no_food_data_reports_no_data(app):
    recipe = Recipe(title="Toast", slug="toast", servings=1)
    recipe.ingredients = [RecipeIngredient(position=0, quantity=2, item="Bread")]
    db.session.add(recipe)
    db.session.commit()

    result = nutrition_for(recipe)
    assert result["has_data"] is False
    assert result["totals"]["kcal"] == 0


def test_shopping_list_merges_matching_units(chili):
    items, loose = shopping_list([(chili, 4), (chili, 4)])
    beef = next(i for i in items if i["item"] == "Ground beef")
    assert beef["quantity"] == 3.0


def test_shopping_list_keeps_unmeasured_items_separate(chili):
    items, loose = shopping_list([(chili, 4)])
    assert any(i["item"] == "Salt" for i in loose)
    assert not any(i["item"] == "Salt" for i in items)
