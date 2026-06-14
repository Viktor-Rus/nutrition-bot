from recipe_categories.bakery import RECIPES as BAKERY_RECIPES
from recipe_categories.desserts import RECIPES as DESSERTS_RECIPES


RECIPES = {
    **{
        recipe_id: {
            **recipe,
            "category": "bakery_desserts",
        }
        for recipe_id, recipe in BAKERY_RECIPES.items()
    },
    **{
        recipe_id: {
            **recipe,
            "category": "bakery_desserts",
        }
        for recipe_id, recipe in DESSERTS_RECIPES.items()
    },
}
