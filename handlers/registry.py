from aiogram import Dispatcher

from handlers import broadcast, feedback, food, memory, pending, recipes, start, support


def register_handlers(dp: Dispatcher):
    start.register(dp)
    support.register(dp)
    broadcast.register(dp)
    recipes.register(dp)
    memory.register(dp)
    feedback.register(dp)
    pending.register(dp)
    food.register(dp)
