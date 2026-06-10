from recipe_categories.bakery import RECIPES as BAKERY_RECIPES
from recipe_categories.desserts import RECIPES as DESSERTS_RECIPES
from recipe_categories.eggs import RECIPES as EGGS_RECIPES
from recipe_categories.fish import RECIPES as FISH_RECIPES
from recipe_categories.meat import RECIPES as MEAT_RECIPES
from recipe_categories.poultry import RECIPES as POULTRY_RECIPES
from recipe_categories.salads import RECIPES as SALADS_RECIPES
from recipe_categories.seafood import RECIPES as SEAFOOD_RECIPES
from recipe_categories.soups import RECIPES as SOUPS_RECIPES
from recipe_categories.vegetarian import RECIPES as VEGETARIAN_RECIPES

RECIPE_CATEGORIES = [
    ("eggs", "Яйца"),
    ("bakery", "Выпечка"),
    ("meat", "Мясо"),
    ("poultry", "Птица"),
    ("seafood", "Морепродукты"),
    ("fish", "Рыба"),
    ("soups", "Супы"),
    ("salads", "Салаты"),
    ("vegetarian", "Овощи и бобовые"),
    ("desserts", "Десерты"),
]

RECIPES = {}

for category_recipes in (
    EGGS_RECIPES,
    BAKERY_RECIPES,
    MEAT_RECIPES,
    POULTRY_RECIPES,
    SEAFOOD_RECIPES,
    FISH_RECIPES,
    SOUPS_RECIPES,
    SALADS_RECIPES,
    VEGETARIAN_RECIPES,
    DESSERTS_RECIPES,
):
    RECIPES.update(category_recipes)
