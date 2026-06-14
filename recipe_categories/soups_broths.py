from recipe_categories.soups import RECIPES as SOUPS_RECIPES


RECIPES = {
    recipe_id: {
        **recipe,
        "category": "soups_broths",
    }
    for recipe_id, recipe in SOUPS_RECIPES.items()
}
