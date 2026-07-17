from aiogram import Dispatcher

from handlers import (
    broadcast,
    chat_member,
    feedback,
    food,
    memory,
    pending,
    recipes,
    start,
    subscriptions,
    support,
)


def register_handlers(dp: Dispatcher):
    chat_member.register(dp)
    start.register(dp)
    subscriptions.register(dp)
    support.register(dp)
    broadcast.register(dp)
    recipes.register(dp)
    memory.register(dp)
    feedback.register(dp)
    pending.register(dp)
    food.register(dp)
