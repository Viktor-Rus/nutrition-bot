from recipe_categories.salads import RECIPES as SALADS_RECIPES
from recipe_categories.vegetarian import RECIPES as VEGETARIAN_RECIPES


RECIPES = {
    **{
        recipe_id: {
            **recipe,
            "category": "vegetables_sides",
        }
        for recipe_id, recipe in VEGETARIAN_RECIPES.items()
    },
    **{
        recipe_id: {
            **recipe,
            "category": "vegetables_sides",
        }
        for recipe_id, recipe in SALADS_RECIPES.items()
    },
}
