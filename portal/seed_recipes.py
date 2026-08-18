"""Starter recipes, so the cookbook is a cookbook rather than an empty grid.

These are placeholders in the sense that nobody in this house wrote them - they
are here to be replaced by the real family recipes. They are not placeholders in
any other sense: the quantities work, the methods are followed through, and the
set is chosen to exercise every part of the cookbook at once.

  - several courses, so the course filter has something to filter
  - overlapping tags, so the tag chips group rather than list
  - ingredient section headings, so "For the sauce" renders
  - quantities that scale into awkward fractions, so the scaler is tested
  - one with no quantity at all ("salt to taste"), which must not break scaling
  - a couple marked favourite, so the home page kitchen panel fills

Ingredients are (quantity, unit, item, note, heading). quantity None means the
line has no number - "to taste" - and heading True makes it a section label.
"""

RECIPES = [
    {
        "title": "Gulf Shrimp Boil",
        "description": (
            "The whole pot in one go — shrimp, corn, sausage and potatoes, "
            "poured out onto newspaper on the table. Cooked outside on the "
            "burner so the kitchen stays cool."
        ),
        "servings": 8, "serving_noun": "people",
        "prep_minutes": 25, "cook_minutes": 30,
        "course": "Dinner", "tags": "seafood, one pot, coastal, crowd",
        "favorite": True,
        "source": "Bayshore, most of a summer",
        "ingredients": [
            (None, None, "For the pot", None, True),
            (5, "quarts", "water", None, False),
            (0.75, "cup", "seafood boil seasoning", "Zatarain's or Old Bay", False),
            (2, None, "lemons", "halved", False),
            (1, "head", "garlic", "cut across the middle", False),
            (None, None, "Going in, in order", None, True),
            (2, "lb", "small red potatoes", None, False),
            (1.5, "lb", "andouille sausage", "cut into 2-inch lengths", False),
            (6, None, "ears of corn", "snapped in half", False),
            (4, "lb", "Gulf shrimp", "shell on, head on if you can get it", False),
            (None, None, "salt", "to taste, after the shrimp are in", False),
        ],
        "instructions": (
            "1. Bring the water, seasoning, lemons and garlic to a hard boil in "
            "the biggest pot you own. Let it boil ten minutes before anything "
            "goes in — this is where the flavour comes from, and skipping it is "
            "why a bland boil is bland.\n\n"
            "2. Potatoes first. Boil 12 minutes, until a knife goes in with "
            "just a little resistance.\n\n"
            "3. Sausage in. 5 minutes.\n\n"
            "4. Corn in. 5 minutes.\n\n"
            "5. Shrimp in, then **turn the heat off**. They are done when they "
            "curl and turn opaque, 2 to 3 minutes. Boiling shrimp is how you get "
            "rubber.\n\n"
            "6. Let everything sit in the hot liquid 10 more minutes to take up "
            "the seasoning, then drain and pour it out on the table."
        ),
        "notes": (
            "Scale the seasoning by volume of water, not by weight of shrimp. "
            "If you double the pot, do two pots — one enormous pot never comes "
            "back to a boil fast enough and the potatoes go to mush waiting."
        ),
    },
    {
        "title": "Chicken and Sausage Gumbo",
        "description": (
            "A dark roux gumbo that takes an afternoon and reheats better than "
            "it serves. Make it the day before."
        ),
        "servings": 6, "serving_noun": "bowls",
        "prep_minutes": 30, "cook_minutes": 150,
        "course": "Dinner", "tags": "cajun, one pot, make ahead, freezer",
        "favorite": True,
        "ingredients": [
            (None, None, "The roux", None, True),
            (1, "cup", "vegetable oil", None, False),
            (1, "cup", "all-purpose flour", None, False),
            (None, None, "The trinity", None, True),
            (2, "cups", "yellow onion", "diced", False),
            (1, "cup", "green bell pepper", "diced", False),
            (1, "cup", "celery", "diced", False),
            (4, "cloves", "garlic", "minced", False),
            (None, None, "Everything else", None, True),
            (2, "lb", "chicken thighs", "boneless, cut into chunks", False),
            (1, "lb", "andouille sausage", "sliced", False),
            (8, "cups", "chicken stock", "warm", False),
            (2, "tsp", "cayenne", "start with one if you are unsure", False),
            (3, None, "bay leaves", None, False),
            (1, "bunch", "green onions", "sliced, for the top", False),
            (6, "cups", "cooked white rice", "to serve", False),
        ],
        "instructions": (
            "1. **The roux is the recipe.** Oil and flour in a heavy pot over "
            "medium, whisking more or less constantly. It will go blonde, then "
            "peanut butter, then copper, then the colour of milk chocolate. That "
            "is 45 minutes to an hour and you cannot walk away from it — if it "
            "smells sharp or shows black flecks, throw it out and start over, "
            "because burnt roux will ruin the whole pot.\n\n"
            "2. The moment it is the right colour, dump in the onion, pepper and "
            "celery. This stops the cooking and is supposed to hiss violently. "
            "Stir 5 minutes until softened, then the garlic for one more.\n\n"
            "3. Whisk in the warm stock a ladle at a time. Cold stock into hot "
            "roux seizes into lumps.\n\n"
            "4. Chicken, sausage, cayenne and bay leaves in. Simmer uncovered "
            "90 minutes, skimming the orange fat off the top as it gathers.\n\n"
            "5. Fish out the bay leaves. Serve over rice with green onions."
        ),
        "notes": (
            "Better on day two, and freezes for three months. Freeze it without "
            "the rice — cooked rice turns to paste in the freezer."
        ),
    },
    {
        "title": "Buttermilk Cornbread",
        "description": "Skillet cornbread with a crust. Not sweet.",
        "servings": 8, "serving_noun": "wedges",
        "prep_minutes": 10, "cook_minutes": 25,
        "course": "Side", "tags": "bread, southern, quick, skillet",
        "ingredients": [
            (3, "tbsp", "bacon grease", "or butter", False),
            (2, "cups", "stone-ground cornmeal", None, False),
            (0.5, "cup", "all-purpose flour", None, False),
            (2, "tsp", "baking powder", None, False),
            (0.5, "tsp", "baking soda", None, False),
            (1.5, "tsp", "salt", None, False),
            (2, "cups", "buttermilk", None, False),
            (2, None, "eggs", None, False),
        ],
        "instructions": (
            "1. Cast iron skillet with the grease in it into the oven, then heat "
            "the oven to 425°F. The skillet heats *with* the oven — putting "
            "batter into a cold pan is how you get pale sides and no crust.\n\n"
            "2. Whisk the dry ingredients. Whisk the buttermilk and eggs "
            "separately, then combine, stirring only until it comes together. "
            "Lumps are fine; overmixing makes it tough.\n\n"
            "3. Pour into the hot skillet — it should sizzle loudly — and bake "
            "20 to 25 minutes until the top springs back.\n\n"
            "4. Turn out onto a board straight away so the bottom does not steam."
        ),
        "notes": "No sugar. If you want sweet cornbread, this is the wrong recipe.",
    },
    {
        "title": "Brisket Chili",
        "description": (
            "Chunks of smoked brisket rather than ground beef, which is what to "
            "do with the flat end nobody wants."
        ),
        "servings": 6, "serving_noun": "bowls",
        "prep_minutes": 20, "cook_minutes": 120,
        "course": "Dinner", "tags": "texas, leftovers, make ahead, slow",
        "ingredients": [
            (3, "lb", "smoked brisket", "cubed, fat and all", False),
            (2, None, "yellow onions", "diced", False),
            (4, "cloves", "garlic", "minced", False),
            (3, "tbsp", "ancho chile powder", None, False),
            (1, "tbsp", "cumin", "ground", False),
            (2, "tsp", "Mexican oregano", None, False),
            (1, "can", "fire-roasted tomatoes", "28 oz", False),
            (2, "cups", "beef stock", None, False),
            (1, "bottle", "dark beer", "12 oz", False),
            (2, "tbsp", "masa harina", "to thicken at the end", False),
        ],
        "instructions": (
            "1. Render the brisket fat in a dutch oven over medium-high, then "
            "brown the cubes in batches. Crowding the pan steams the meat.\n\n"
            "2. Onions into the fat, 8 minutes until they have some colour. "
            "Garlic, chile powder, cumin and oregano for 60 seconds — until the "
            "spices smell toasted, no longer, or they turn bitter.\n\n"
            "3. Beer in, scraping everything off the bottom. Reduce by half.\n\n"
            "4. Tomatoes, stock and the brisket back in. Simmer partly covered "
            "90 minutes.\n\n"
            "5. Whisk the masa with a little water, stir it in, and cook 10 more "
            "minutes to thicken."
        ),
        "notes": "No beans. Argue about it somewhere else.",
    },
    {
        "title": "Pimento Cheese",
        "description": "Ten minutes, no cooking, and it is better after a day in the fridge.",
        "servings": 12, "serving_noun": "servings",
        "prep_minutes": 10, "cook_minutes": 0,
        "course": "Appetizer", "tags": "southern, no cook, make ahead, party",
        "ingredients": [
            (1, "lb", "sharp cheddar", "grated from a block, not pre-shredded", False),
            (0.75, "cup", "mayonnaise", "Duke's", False),
            (4, "oz", "pimentos", "drained and chopped", False),
            (2, "oz", "cream cheese", "softened", False),
            (1, "tsp", "onion powder", None, False),
            (0.5, "tsp", "cayenne", None, False),
            (None, None, "black pepper", "to taste", False),
        ],
        "instructions": (
            "1. Grate the cheddar yourself. Pre-shredded cheese is coated in "
            "starch to stop it clumping, and that starch makes pimento cheese "
            "chalky — this is the one step that decides whether it is good.\n\n"
            "2. Mash everything together with a fork. Not a food processor, "
            "unless you want a paste.\n\n"
            "3. Cover and refrigerate at least an hour, ideally overnight."
        ),
    },
    {
        "title": "Skillet Green Beans with Bacon",
        "description": "Blistered rather than boiled, so they keep some bite.",
        "servings": 4, "serving_noun": "servings",
        "prep_minutes": 10, "cook_minutes": 15,
        "course": "Side", "tags": "quick, vegetable, skillet",
        "ingredients": [
            (1, "lb", "green beans", "trimmed", False),
            (4, "slices", "thick-cut bacon", "chopped", False),
            (3, "cloves", "garlic", "sliced thin", False),
            (1, "tbsp", "cider vinegar", None, False),
            (None, None, "salt and pepper", "to taste", False),
        ],
        "instructions": (
            "1. Render the bacon in a wide skillet over medium until crisp. "
            "Lift it out, leave the fat.\n\n"
            "2. Beans into the hot fat in a single layer. Leave them alone 3 "
            "minutes to blister before stirring — a crowded, constantly-stirred "
            "pan steams instead.\n\n"
            "3. Garlic for 30 seconds, then a splash of water and a lid for 3 "
            "minutes.\n\n"
            "4. Lid off, vinegar in, bacon back. Salt and pepper."
        ),
    },
    {
        "title": "Peach Cobbler",
        "description": (
            "The batter goes under the fruit and rises through it. Gulf Coast "
            "peaches in July, otherwise frozen."
        ),
        "servings": 8, "serving_noun": "servings",
        "prep_minutes": 15, "cook_minutes": 45,
        "course": "Dessert", "tags": "summer, fruit, crowd, classic",
        "favorite": True,
        "ingredients": [
            (None, None, "The fruit", None, True),
            (6, "cups", "peaches", "peeled and sliced", False),
            (0.5, "cup", "sugar", None, False),
            (1, "tbsp", "lemon juice", None, False),
            (None, None, "The batter", None, True),
            (0.5, "cup", "butter", None, False),
            (1, "cup", "all-purpose flour", None, False),
            (1, "cup", "sugar", None, False),
            (2, "tsp", "baking powder", None, False),
            (0.25, "tsp", "salt", None, False),
            (1, "cup", "whole milk", None, False),
        ],
        "instructions": (
            "1. Oven to 350°F. Butter into a 9x13 dish and put it in the oven to "
            "melt while it heats.\n\n"
            "2. Toss the peaches with their sugar and the lemon juice. Leave "
            "them 10 minutes to draw out some juice.\n\n"
            "3. Whisk the flour, sugar, baking powder and salt, then the milk, "
            "into a loose batter.\n\n"
            "4. Pour the batter over the melted butter — **do not stir**. Spoon "
            "the peaches and their juice over the batter — still do not stir. "
            "The layers sort themselves out in the oven, and stirring is how you "
            "get one dense sweet brick.\n\n"
            "5. Bake 45 minutes until the top is deep gold and the edges bubble."
        ),
        "notes": "Vanilla ice cream, while it is still too hot to eat sensibly.",
    },
    {
        "title": "Migas",
        "description": "Saturday breakfast. Stale tortillas are the point.",
        "servings": 4, "serving_noun": "servings",
        "prep_minutes": 10, "cook_minutes": 12,
        "course": "Breakfast", "tags": "tex-mex, quick, eggs, leftovers",
        "ingredients": [
            (6, None, "corn tortillas", "cut in strips, day old", False),
            (3, "tbsp", "vegetable oil", None, False),
            (8, None, "eggs", "beaten", False),
            (0.5, None, "white onion", "diced", False),
            (1, None, "jalapeño", "seeded and diced", False),
            (1, "cup", "Monterey Jack", "grated", False),
            (None, None, "salsa, cilantro, lime", "to serve", False),
        ],
        "instructions": (
            "1. Fry the tortilla strips in the oil until they stop bending and "
            "start snapping, 3 to 4 minutes. Drain on paper.\n\n"
            "2. Same pan, most of the oil poured off. Onion and jalapeño 3 "
            "minutes.\n\n"
            "3. Eggs in, low heat, pushed slowly around the pan. When they are "
            "still a little wetter than you want them, the strips and cheese go "
            "back in — the residual heat finishes both.\n\n"
            "4. Straight onto plates. Migas do not wait."
        ),
    },
    {
        "title": "Red Beans and Rice",
        "description": "Monday food. Soak the beans Sunday night.",
        "servings": 6, "serving_noun": "bowls",
        "prep_minutes": 15, "cook_minutes": 180,
        "course": "Dinner", "tags": "cajun, cheap, make ahead, one pot",
        "ingredients": [
            (1, "lb", "dried red kidney beans", "soaked overnight", False),
            (1, "lb", "andouille sausage", "sliced", False),
            (1, None, "smoked ham hock", None, False),
            (1, None, "yellow onion", "diced", False),
            (1, None, "green bell pepper", "diced", False),
            (2, "stalks", "celery", "diced", False),
            (4, "cloves", "garlic", "minced", False),
            (2, "tsp", "Creole seasoning", None, False),
            (3, None, "bay leaves", None, False),
            (6, "cups", "water", None, False),
            (4, "cups", "cooked white rice", "to serve", False),
        ],
        "instructions": (
            "1. Brown the sausage in a heavy pot. Lift it out.\n\n"
            "2. Onion, pepper and celery in the fat, 8 minutes. Garlic one more.\n\n"
            "3. Drained beans, ham hock, seasoning, bay leaves and water. Bring "
            "up, then down to a bare simmer, lid ajar, 2.5 to 3 hours.\n\n"
            "4. At the end, mash a cup of the beans against the side of the pot "
            "and stir them back in. That is what makes it creamy — there is no "
            "cream in it.\n\n"
            "5. Sausage back in for the last 20 minutes. Pull the meat off the "
            "hock, discard the bay leaves, serve over rice."
        ),
        "notes": "Salt only at the end. Salted early, the bean skins stay tough.",
    },
    {
        "title": "Front Porch Sweet Tea",
        "description": "A gallon at a time, because it never lasts.",
        "servings": 16, "serving_noun": "glasses",
        "prep_minutes": 5, "cook_minutes": 10,
        "course": "Drink", "tags": "southern, summer, crowd, no cook",
        "ingredients": [
            (1, "gallon", "water", "divided", False),
            (6, "bags", "black tea", "family size", False),
            (1.5, "cups", "sugar", None, False),
            (0.125, "tsp", "baking soda", None, False),
            (1, None, "lemon", "sliced, to serve", False),
        ],
        "instructions": (
            "1. Boil 4 cups of the water. Off the heat, add the tea bags and the "
            "baking soda and steep 10 minutes. The pinch of soda takes the "
            "bitter edge off and stops it going cloudy in the fridge.\n\n"
            "2. Lift the bags out without squeezing them. Squeezing is where "
            "bitterness comes from.\n\n"
            "3. Stir the sugar into the hot tea until it is fully dissolved, "
            "then top up to a gallon with cold water.\n\n"
            "4. Refrigerate. Serve over a lot of ice with lemon."
        ),
    },
]
