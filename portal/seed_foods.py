"""A starter nutrition table.

Figures are per 100 g, from USDA FoodData Central reference values, rounded.
`units` gives the weight in grams of one of that measure, which is what lets
the portal turn "2 cups flour" into a number it can add up. `each` is used for
things that are counted rather than measured.

These are averages for the generic item - they are close enough to be useful,
not exact for a particular brand. Anything here can be corrected under
Settings -> Food data, and none of it is needed for a recipe to work; it only
powers the nutrition panel.

Columns: name, kcal, protein, carbs, fat, fiber, sodium(mg), units
"""

FOODS = [
    # --- meat, fish, eggs ------------------------------------------------
    ("Chicken breast, boneless raw", 165, 31, 0, 3.6, 0, 74, {"each": 174}),
    ("Chicken thigh, boneless raw", 209, 26, 0, 10.9, 0, 84, {"each": 90}),
    ("Ground beef, 80/20", 254, 17.2, 0, 20, 0, 66, {}),
    ("Ground turkey, 93/7", 150, 19, 0, 8.3, 0, 70, {}),
    ("Chuck roast, raw", 217, 18.7, 0, 15.4, 0, 66, {}),
    ("Pork chop, raw", 172, 21, 0, 9, 0, 55, {"each": 170}),
    ("Bacon, raw", 458, 12, 1.3, 45, 0, 662, {"each": 28}),
    ("Andouille sausage", 301, 15.9, 3.1, 24.6, 0, 1080, {}),
    ("Shrimp, raw", 85, 20.1, 0.9, 0.5, 0, 119, {}),
    ("Salmon fillet, raw", 208, 20.4, 0, 13.4, 0, 59, {}),
    ("Tilapia, raw", 96, 20.1, 0, 1.7, 0, 52, {}),
    ("Large egg", 143, 12.6, 0.7, 9.5, 0, 142, {"each": 50}),

    # --- beans -----------------------------------------------------------
    ("Black beans, canned drained", 91, 6, 16.6, 0.3, 6.9, 265, {"cup": 172}),
    ("Pinto beans, canned drained", 88, 5.4, 16, 0.7, 5.5, 258, {"cup": 171}),
    ("Chickpeas, canned drained", 139, 7.1, 22.5, 2.6, 6.4, 246, {"cup": 164}),

    # --- dairy -----------------------------------------------------------
    ("Whole milk", 61, 3.2, 4.8, 3.3, 0, 43, {"cup": 244, "tbsp": 15}),
    ("Buttermilk", 40, 3.3, 4.8, 0.9, 0, 105, {"cup": 245}),
    ("Heavy cream", 340, 2.8, 2.7, 36, 0, 27, {"cup": 238, "tbsp": 15}),
    ("Butter", 717, 0.9, 0.1, 81, 0, 11, {"cup": 227, "tbsp": 14, "stick": 113}),
    ("Cheddar cheese, shredded", 403, 23, 3.4, 33, 0, 653, {"cup": 113}),
    ("Monterey Jack, shredded", 373, 24.5, 0.7, 30, 0, 536, {"cup": 113}),
    ("Parmesan, grated", 420, 38, 4.1, 28, 0, 1600, {"cup": 100, "tbsp": 5}),
    ("Sour cream", 198, 2.4, 4.6, 19.4, 0, 51, {"cup": 230, "tbsp": 14}),
    ("Cream cheese", 342, 6, 4.1, 34, 0, 321, {"tbsp": 14, "cup": 232}),
    ("Plain yogurt, whole milk", 61, 3.5, 4.7, 3.3, 0, 46, {"cup": 245}),

    # --- grains and starches --------------------------------------------
    ("All-purpose flour", 364, 10.3, 76.3, 1, 2.7, 2, {"cup": 120, "tbsp": 8}),
    ("Cornmeal", 370, 8.1, 79.5, 3.6, 7.3, 7, {"cup": 122}),
    ("White rice, raw", 365, 7.1, 80, 0.7, 1.3, 5, {"cup": 185}),
    ("Brown rice, raw", 370, 7.9, 77, 2.9, 3.5, 7, {"cup": 185}),
    ("Rolled oats", 389, 16.9, 66.3, 6.9, 10.6, 2, {"cup": 90}),
    ("Spaghetti, dry", 371, 13, 74.7, 1.5, 3.2, 6, {}),
    ("White bread", 266, 9, 49, 3.2, 2.7, 490, {"slice": 28}),
    ("Flour tortilla", 306, 8.2, 51.4, 7.4, 3.1, 610, {"each": 45}),
    ("Corn tortilla", 218, 5.7, 44.6, 2.9, 6.3, 45, {"each": 26}),
    ("Potatoes", 77, 2, 17.5, 0.1, 2.2, 6, {"each": 173, "cup": 150}),
    ("Sweet potato", 86, 1.6, 20.1, 0.1, 3, 55, {"each": 130, "cup": 133}),

    # --- vegetables ------------------------------------------------------
    ("Yellow onion", 40, 1.1, 9.3, 0.1, 1.7, 4, {"each": 110, "cup": 160}),
    ("Garlic", 149, 6.4, 33, 0.5, 2.1, 17, {"clove": 3, "each": 3}),
    ("Carrots", 41, 0.9, 9.6, 0.2, 2.8, 69, {"each": 61, "cup": 128}),
    ("Celery", 16, 0.7, 3, 0.2, 1.6, 80, {"stalk": 40, "cup": 101}),
    ("Bell pepper", 31, 1, 6, 0.3, 2.1, 4, {"each": 119, "cup": 149}),
    ("Jalapeño", 29, 0.9, 6.5, 0.4, 2.8, 3, {"each": 14}),
    ("Tomatoes", 18, 0.9, 3.9, 0.2, 1.2, 5, {"each": 123, "cup": 180}),
    ("Crushed tomatoes, canned", 32, 1.6, 7.3, 0.3, 1.9, 186, {"cup": 245}),
    ("Tomato paste", 82, 4.3, 18.9, 0.5, 4.1, 59, {"tbsp": 16, "cup": 262}),
    ("Corn kernels", 86, 3.3, 19, 1.4, 2, 15, {"cup": 154, "each": 90}),
    ("Broccoli", 34, 2.8, 6.6, 0.4, 2.6, 33, {"cup": 91}),
    ("Green beans", 31, 1.8, 7, 0.2, 2.7, 6, {"cup": 100}),
    ("Spinach", 23, 2.9, 3.6, 0.4, 2.2, 79, {"cup": 30}),
    ("Romaine lettuce", 17, 1.2, 3.3, 0.3, 2.1, 8, {"cup": 47}),
    ("Mushrooms", 22, 3.1, 3.3, 0.3, 1, 5, {"cup": 70}),
    ("Cabbage", 25, 1.3, 5.8, 0.1, 2.5, 18, {"cup": 89}),

    # --- fruit -----------------------------------------------------------
    ("Apple", 52, 0.3, 13.8, 0.2, 2.4, 1, {"each": 182, "cup": 125}),
    ("Banana", 89, 1.1, 22.8, 0.3, 2.6, 1, {"each": 118, "cup": 150}),
    ("Orange", 47, 0.9, 11.8, 0.1, 2.4, 0, {"each": 131}),
    ("Strawberries", 32, 0.7, 7.7, 0.3, 2, 1, {"cup": 152}),
    ("Avocado", 160, 2, 8.5, 14.7, 6.7, 7, {"each": 201}),
    ("Lemon juice", 22, 0.4, 6.9, 0.2, 0.3, 1, {"tbsp": 15, "cup": 244}),
    ("Lime juice", 25, 0.4, 8.4, 0.1, 0.4, 2, {"tbsp": 15, "cup": 242}),

    # --- fats and condiments ---------------------------------------------
    ("Olive oil", 884, 0, 0, 100, 0, 2, {"cup": 216, "tbsp": 13.5}),
    ("Vegetable oil", 884, 0, 0, 100, 0, 0, {"cup": 218, "tbsp": 13.6}),
    ("Mayonnaise", 680, 1, 0.6, 75, 0, 635, {"tbsp": 14, "cup": 220}),
    ("Ketchup", 101, 1.2, 25.8, 0.1, 0.3, 907, {"tbsp": 17}),
    ("Soy sauce", 53, 8.1, 4.9, 0.6, 0.8, 5493, {"tbsp": 16}),
    ("Honey", 304, 0.3, 82.4, 0, 0.2, 4, {"tbsp": 21, "cup": 339}),
    ("Peanut butter", 588, 25.1, 20, 50.4, 6, 429, {"tbsp": 16, "cup": 258}),

    # --- baking ----------------------------------------------------------
    ("Granulated sugar", 387, 0, 100, 0, 0, 1, {"cup": 200, "tbsp": 12.5}),
    ("Brown sugar", 380, 0.1, 98.1, 0, 0, 28, {"cup": 220, "tbsp": 13.8}),
    ("Powdered sugar", 389, 0, 99.8, 0, 0, 2, {"cup": 120}),
    ("Cornstarch", 381, 0.3, 91.3, 0.1, 0.9, 9, {"tbsp": 8, "cup": 128}),
    ("Cocoa powder", 228, 19.6, 57.9, 13.7, 37, 21, {"cup": 86, "tbsp": 5.4}),
    ("Semisweet chocolate chips", 480, 4.2, 63.9, 30, 5.9, 11, {"cup": 170}),
    ("Baking powder", 53, 0, 27.7, 0, 0.2, 10600, {"tsp": 4.6}),
    ("Baking soda", 0, 0, 0, 0, 0, 27360, {"tsp": 4.8}),
    ("Vanilla extract", 288, 0.1, 12.7, 0.1, 0, 9, {"tsp": 4.2, "tbsp": 13}),

    # --- liquids and seasoning -------------------------------------------
    ("Chicken broth", 4, 0.5, 0.4, 0.1, 0, 343, {"cup": 240}),
    ("Beef broth", 5, 0.9, 0.1, 0.2, 0, 371, {"cup": 240}),
    ("Water", 0, 0, 0, 0, 0, 0, {"cup": 237, "tbsp": 15}),
    ("Salt", 0, 0, 0, 0, 0, 38758, {"tsp": 6, "tbsp": 18}),
    ("Black pepper", 251, 10.4, 63.9, 3.3, 25.3, 20, {"tsp": 2.3}),
    ("Chili powder", 282, 13.5, 49.7, 14.3, 34.8, 1640, {"tsp": 2.7, "tbsp": 8}),
    ("Ground cumin", 375, 17.8, 44.2, 22.3, 10.5, 168, {"tsp": 2, "tbsp": 6}),
    ("Paprika", 282, 14.1, 53.9, 12.9, 34.9, 68, {"tsp": 2.3, "tbsp": 6.8}),
]
