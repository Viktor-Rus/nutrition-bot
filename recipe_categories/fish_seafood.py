from recipe_categories.fish import RECIPES as FISH_RECIPES
from recipe_categories.seafood import RECIPES as SEAFOOD_RECIPES


RECIPES = {
    **{
        recipe_id: {
            **recipe,
            "category": "fish_seafood",
        }
        for recipe_id, recipe in FISH_RECIPES.items()
    },
    **{
        recipe_id: {
            **recipe,
            "category": "fish_seafood",
        }
        for recipe_id, recipe in SEAFOOD_RECIPES.items()
    },
}
