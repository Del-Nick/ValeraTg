from pprint import pprint

import pymorphy3
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

morph = pymorphy3.MorphAnalyzer()


def get_sex_of_person_by_name(name: str) -> str:
    parsed_word = morph.parse(name)
    if parsed_word[0].tag.gender:
        return parsed_word[0].tag.gender[0]
    else:
        return '0'


async def remove_inline_keyboard(bot: Bot, message: Message):
    try:
        await bot.edit_message_reply_markup(chat_id=message.chat.id,
                                            message_id=message.message_id - 1,
                                            reply_markup=None)
    except TelegramBadRequest:
        pass


def escape_markdown(text: str) -> str:
    escape_chars = r"\*_`[]()~>#+-=|{}.!"
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

