from aiogram import Dispatcher, types
from aiogram.filters import Command

from services.broadcast import (
    cancel_broadcast,
    confirm_broadcast,
    create_broadcast_draft,
)


def register(dp: Dispatcher):
    @dp.message(Command("broadcast"))
    async def broadcast_command(message: types.Message):
        await create_broadcast_draft(message)

    @dp.message(Command("confirm_broadcast"))
    async def confirm_broadcast_command(message: types.Message):
        await confirm_broadcast(message)

    @dp.message(Command("cancel_broadcast"))
    async def cancel_broadcast_command(message: types.Message):
        await cancel_broadcast(message)
