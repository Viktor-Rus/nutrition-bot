from aiogram import Dispatcher, types

from services.users import set_user_blocked, upsert_user_profile


def register(dp: Dispatcher):
    @dp.my_chat_member()
    async def bot_chat_member_updated(event: types.ChatMemberUpdated):
        if event.chat.type != "private":
            return

        user_id = event.chat.id
        new_status = event.new_chat_member.status

        if new_status in ("kicked", "left"):
            set_user_blocked(user_id, True)
            print("USER BLOCKED BOT:", user_id)
            return

        if new_status == "member":
            upsert_user_profile(event.from_user)
            set_user_blocked(user_id, False)
            print("USER UNBLOCKED BOT:", user_id)
