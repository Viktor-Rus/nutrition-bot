from recipe_categories.bakery_desserts import RECIPES as BAKERY_DESSERTS_RECIPES
from recipe_categories.drinks import RECIPES as DRINKS_RECIPES
from recipe_categories.eggs import RECIPES as EGGS_RECIPES
from recipe_categories.fish_seafood import RECIPES as FISH_SEAFOOD_RECIPES
from recipe_categories.grains_seeds import RECIPES as GRAINS_SEEDS_RECIPES
from recipe_categories.lifehacks import RECIPES as LIFEHACKS_RECIPES
from recipe_categories.meat_offal import RECIPES as MEAT_OFFAL_RECIPES
from recipe_categories.poultry import RECIPES as POULTRY_RECIPES
from recipe_categories.preserves import RECIPES as PRESERVES_RECIPES
from recipe_categories.soups_broths import RECIPES as SOUPS_BROTHS_RECIPES
from recipe_categories.vegetables_sides import RECIPES as VEGETABLES_SIDES_RECIPES

RECIPE_CATEGORIES = [
    ("soups_broths", "Супы и бульоны"),
    ("poultry", "Птица"),
    ("meat_offal", "Мясо и субпродукты"),
    ("fish_seafood", "Рыба и морепродукты"),
    ("eggs", "Яйца"),
    ("vegetables_sides", "Овощи и гарниры"),
    ("grains_seeds", "Злаки и семена"),
    ("preserves", "Заготовки"),
    ("bakery_desserts", "Выпечка и десерты"),
    ("drinks", "Напитки"),
    ("lifehacks", "Лайфхаки"),
]

RECIPES = {}

for category_recipes in (
    SOUPS_BROTHS_RECIPES,
    POULTRY_RECIPES,
    MEAT_OFFAL_RECIPES,
    FISH_SEAFOOD_RECIPES,
    EGGS_RECIPES,
    VEGETABLES_SIDES_RECIPES,
    GRAINS_SEEDS_RECIPES,
    PRESERVES_RECIPES,
    BAKERY_DESSERTS_RECIPES,
    DRINKS_RECIPES,
    LIFEHACKS_RECIPES,
):
    RECIPES.update(category_recipes)
