from aiogram import Dispatcher, types
from aiogram.filters import Command

from services.support import send_support_direct_message, send_support_reply


def register(dp: Dispatcher):
    @dp.message(Command("reply"))
    async def reply_command(message: types.Message):
        await send_support_reply(message)

    @dp.message(Command("send"))
    async def send_command(message: types.Message):
        await send_support_direct_message(message)
