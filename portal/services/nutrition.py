"""Scaling a recipe up or down, and adding up nutrition when it is known.

Scaling always works. Nutrition only fills in for ingredients linked to a Food
entry - the rest are reported as "not counted" rather than silently ignored, so
a total is never quietly wrong.
"""

# Grams for one unit, used when a Food has no override of its own.
DEFAULT_UNIT_GRAMS = {
    "g": 1, "gram": 1, "grams": 1,
    "kg": 1000,
    "oz": 28.3495, "ounce": 28.3495, "ounces": 28.3495,
    "lb": 453.592, "lbs": 453.592, "pound": 453.592, "pounds": 453.592,
    "ml": 1, "milliliter": 1,
    "l": 1000, "liter": 1000,
    "cup": 240, "cups": 240,
    "tbsp": 15, "tablespoon": 15, "tablespoons": 15,
    "tsp": 5, "teaspoon": 5, "teaspoons": 5,
    "pint": 473, "quart": 946, "gallon": 3785,
}

NUTRIENTS = ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "sodium_mg")

NUTRIENT_LABELS = {
    "kcal": ("Calories", ""),
    "protein_g": ("Protein", "g"),
    "carbs_g": ("Carbs", "g"),
    "fat_g": ("Fat", "g"),
    "fiber_g": ("Fiber", "g"),
    "sodium_mg": ("Sodium", "mg"),
}


def normalise_unit(unit):
    return (unit or "").strip().lower().rstrip(".")


def grams_for(ingredient, quantity):
    """Best guess at the gram weight of `quantity` of this ingredient."""
    if quantity is None:
        return None
    unit = normalise_unit(ingredient.unit)
    food = ingredient.food

    if food is not None:
        overrides = food.unit_grams
        # An empty unit means "2 eggs" - look for an 'each' weight.
        key = unit or "each"
        if key in overrides:
            return quantity * float(overrides[key])

    if not unit:
        return None  # a count of something with no known per-item weight
    if unit in DEFAULT_UNIT_GRAMS:
        return quantity * DEFAULT_UNIT_GRAMS[unit]
    return None


def scale_ingredients(recipe, servings):
    """Return ingredient rows scaled to `servings`."""
    base = recipe.servings or 1
    factor = (servings or base) / base

    rows = []
    for ing in recipe.ingredients:
        qty = None if ing.quantity is None else ing.quantity * factor
        rows.append(
            {
                "id": ing.id,
                "heading": ing.heading,
                "quantity": qty,
                "base_quantity": ing.quantity,
                "unit": ing.unit,
                "item": ing.item,
                "note": ing.note,
                "food": ing.food,
                "grams": grams_for(ing, qty),
            }
        )
    return rows, factor


def nutrition_for(recipe, servings=None):
    """Totals for the whole recipe and per serving.

    Returns counted/uncounted so the template can be honest about coverage.
    """
    servings = servings or recipe.servings or 1
    rows, _ = scale_ingredients(recipe, servings)

    totals = {k: 0.0 for k in NUTRIENTS}
    counted, uncounted = [], []

    for row in rows:
        if row["heading"]:
            continue
        food, grams = row["food"], row["grams"]
        if food is None or grams is None:
            uncounted.append(row["item"])
            continue
        share = grams / 100.0
        for key in NUTRIENTS:
            totals[key] += (getattr(food, key) or 0) * share
        counted.append(row["item"])

    per_serving = {k: (v / servings if servings else 0) for k, v in totals.items()}
    total_items = len(counted) + len(uncounted)

    return {
        "totals": totals,
        "per_serving": per_serving,
        "servings": servings,
        "counted": counted,
        "uncounted": uncounted,
        "coverage": (len(counted) / total_items) if total_items else 0,
        "has_data": bool(counted),
    }


def shopping_list(recipes_with_servings):
    """Merge several recipes into one list, combining like units.

    recipes_with_servings: [(recipe, servings), ...]
    """
    merged = {}
    loose = []
    for recipe, servings in recipes_with_servings:
        rows, _ = scale_ingredients(recipe, servings)
        for row in rows:
            if row["heading"]:
                continue
            key = (row["item"].strip().lower(), normalise_unit(row["unit"]))
            if row["quantity"] is None:
                loose.append({"item": row["item"], "note": row["note"],
                              "from": recipe.title})
                continue
            if key in merged:
                merged[key]["quantity"] += row["quantity"]
                merged[key]["from"].append(recipe.title)
            else:
                merged[key] = {
                    "item": row["item"],
                    "unit": row["unit"],
                    "quantity": row["quantity"],
                    "from": [recipe.title],
                }
    items = sorted(merged.values(), key=lambda r: r["item"].lower())
    return items, loose
