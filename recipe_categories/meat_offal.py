from recipe_categories.meat import RECIPES as MEAT_RECIPES


RECIPES = {
    recipe_id: {
        **recipe,
        "category": "meat_offal",
    }
    for recipe_id, recipe in MEAT_RECIPES.items()
}
