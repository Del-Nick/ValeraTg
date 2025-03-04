import asyncio
import sys
from datetime import datetime
from loguru import logger

from aiogram import Dispatcher, Bot, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.command import Command
from aiogram.types import Message, CallbackQuery

from Admin.Admin import admin_handler
from Config.Config import global_settings
from Handlers.Event import event_handler
from Handlers.Headman import headman_handler
from Handlers.Keyboards import empty_keyboard, standard_keyboard
from Handlers.Registration import registration
from Handlers.Settings import settings_handler
from Handlers.StartMenu import back_to_start, start_menu
from Scripts.FloorCabinetSearchEngine import check_rooms, rooms
from Scripts.Others import remove_inline_keyboard
from Server.Core import DB, QuizUserDB
from Server.Models import User, TgMessages

bot = Bot(token=global_settings.main_token) if global_settings.MAIN_BOT else Bot(token=global_settings.test_bot_token)
dp = Dispatcher()

logger.add('log.txt', format="{time} {level} {message}", level="ERROR")


async def print_messages(user: User, message: Message = None, callback: CallbackQuery = None):
    if message:
        tg_message = TgMessages(TgName=user.TgName, action=message.text, type_action='types.Message')
        print(f'{datetime.now()}    {user.TgName}:      {message.text}      types.Message')
    else:
        tg_message = TgMessages(TgName=user.TgName, action=callback.data, type_action='types.Message')
        print(f'{datetime.now()}    {user.TgName}:      {callback.data}     types.CallbackQuery')

    await DB.insert_tg_messages(tg_message)


@dp.message(Command('start'))
async def cmd_start(message: Message):
    user = await DB.select_manager(message)
    quiz_user = await QuizUserDB.select(user_id=user.ID)

    if quiz_user:
        if not quiz_user.end_datetime:
            return

    if not user.settings.pause:
        if user.groups:
            await back_to_start(user, message, bot)
        else:
            user.action = 'registration_first_message'
            await registration(bot=bot, user=user, message=message)

        await DB.update_user(user)

    await print_messages(user, message=message)


@dp.message(Command('valera'))
async def cmd_valera(message: Message):
    user = await DB.select_manager(message)
    quiz_user = await QuizUserDB.select(user_id=user.ID)

    if quiz_user:
        if not quiz_user.end_datetime:
            return

    if not user.settings.pause:
        if user.groups:
            await back_to_start(user, message, bot)

        else:
            await message.answer(text='Напиши мне свою учебную группу',
                                 reply_markup=empty_keyboard())
            user.action = 'registration_add_group'

        await DB.update_user(user)

    await print_messages(user, message=message)


@dp.message(Command('pause'))
async def cmd_pause(message: Message):
    user = await DB.select_manager(message)
    quiz_user = await QuizUserDB.select(user_id=user.ID)

    if quiz_user:
        if not quiz_user.end_datetime:
            return

    if user.settings.pause:
        await message.answer(text='Я вернулся!',
                             reply_markup=standard_keyboard(user).as_markup())
    else:
        await message.answer(text='Я больше не буду реагировать на твои сообщения. Чтобы возобновить работу, '
                                  'вызови команду ещё раз')

    user.settings.pause = not user.settings.pause
    await DB.update_user(user)

    try:
        await bot.edit_message_reply_markup(chat_id=message.chat.id,
                                            message_id=message.message_id - 1,
                                            reply_markup=None)
    except TelegramBadRequest:
        pass


@dp.message(Command('delete'))
async def cmd_delete(message: Message):
    user = await DB.select_manager(message)

    await message.answer(text='Пользователь будет удалён через 3 секунды')

    for _ in range(2, -1, -1):
        await asyncio.sleep(1)
        await bot.edit_message_text(
            text=f'Пользователь будет удалён через {_} секунды',
            chat_id=message.from_user.id,
            message_id=message.message_id + 1
        )

    await DB.delete_user(user)

    stop = message.message_id - 100 if message.message_id > 100 else 100

    for _ in range(message.message_id + 1, stop, -1):
        try:
            await bot.delete_message(
                chat_id=message.from_user.id,
                message_id=_)
        except TelegramBadRequest:
            pass


@dp.message(F.text.startswith('Валер'))
async def to_start_handler(message: Message):
    user = await DB.select_manager(message)
    if not user.settings.pause:
        await back_to_start(user, message, bot)
        await DB.update_user(user)

    await print_messages(user, message=message)


@dp.callback_query()
async def callback_handler(callback: CallbackQuery):
    user = await DB.select_manager(callback.message)

    if not user.settings.pause:
        if callback.data.startswith('start'):
            await start_menu(bot=bot, user=user, callback=callback)

        elif callback.data.startswith('registration'):
            await registration(bot=bot, user=user, callback=callback)

        elif callback.data.startswith('settings'):
            await settings_handler(user=user, bot=bot, callback=callback)

        elif callback.data.startswith('headman'):
            await headman_handler(bot=bot, user=user, callback=callback)

        elif callback.data.startswith('admin'):
            await admin_handler(bot=bot, admin=user, callback=callback)

        # elif callback.data.startswith('event'):
        #     await event_handler(bot=bot, user=user, callback=callback)

    await print_messages(user, callback=callback)
    await DB.update_user(user)


@dp.message()
async def message_handler(message: Message):
    user = await DB.select_manager(message)

    if not user.settings.pause:
        if user.action.startswith('registration'):
            await registration(bot=bot, user=user, message=message)

        elif message.text == 'я админ':
            if user.TgID in global_settings.admins:
                await remove_inline_keyboard(bot, message)
                await message.answer('И не поспоришь',
                                     reply_markup=standard_keyboard(user).as_markup())
                user.settings.admin = True
            else:
                await remove_inline_keyboard(bot, message)
                await message.answer('Не уверен 🤨',
                                     reply_markup=standard_keyboard(user).as_markup())

        elif user.action.startswith('settings'):
            await settings_handler(user=user, bot=bot, message=message)

        elif user.action.startswith('start'):
            await start_menu(bot=bot, user=user, message=message)

        elif user.action.startswith('admin'):
            await admin_handler(bot=bot, admin=user, message=message)

        elif user.action.startswith('headman'):
            await headman_handler(bot=bot, user=user, message=message)

        elif message.document:
            # await message.answer_document(document=message.document.file_id,
            #                               caption=f'file_id = {message.document.file_id}')
            pass

        elif message.photo:
            pass

        else:
            await remove_inline_keyboard(bot, message)
            await message.answer(text='Не совсем тебя понял')

    await remove_inline_keyboard(bot, message)
    await print_messages(user, message=message)
    await DB.update_user(user)


@logger.catch
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
