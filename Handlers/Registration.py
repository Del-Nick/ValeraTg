from aiogram import Bot
from aiogram.types import Message, CallbackQuery
import difflib

from Server.Models import User
from Server.Core import DB
from Scripts.RequestsToVK import get_user_data_by_id
from Scripts.Arrays import GROUPS
from Handlers.Keyboards import *


async def registration(bot: Bot, user: User, message: Message = None, callback: CallbackQuery = None):
    if callback:
        if callback.data.startswith('registration_add_group'):
            await add_group(bot=bot, user=user, callback=callback)

    else:
        if 'first_message' in user.action:
            await message.answer(text=f'Привет, {user.TgName}! Меня зовут Валера, я твой чат-бот. Если вдруг ты '
                                      f'запутался и не знаешь выход, просто позови меня по имени, и я тебя вытащу.')

            await message.answer(text=r'Давай немного познакомимся\. Для полноценной работы мне необходимо знать твой '
                                      r'ID ВКонтакте или короткое имя *@nickname*\. '
                                      r'Это нужно для синхронизации работы в двух социальных сетях\. '
                                      r'Дальше ты сможешь пользоваться любой',
                                 reply_markup=later_keyboard(),
                                 parse_mode='MarkdownV2')

            user.action = 'registration_get_vk_id'

        elif 'get_vk_id' in user.action:
            await get_vk_id(user=user, message=message)

        elif 'add_group' in user.action:
            await add_group(bot=bot, user=user, message=message)


async def get_vk_id(user: User, message: Message):
    if message.text == 'Напишу позже':
        await message.answer(text='Напиши мне свою учебную группу',
                             reply_markup=empty_keyboard())
        user.action = 'registration_add_group'
    else:
        user_vk_data = await get_user_data_by_id(user, user_id=message.text.replace('@', ''))

        if user_vk_data:
            VkID, first_name, last_name, sex = user_vk_data

            if await DB.check_user_exists(VkID=VkID):
                await DB.merge_records(user, VkID)
                user = await DB.select_user(user.TgID)

            else:
                user.VkID, user.VkFirstName, user.VkLastName, user.sex = VkID, first_name, last_name, sex

            if user.groups:
                await message.answer('Загружаю данные из ВК...',
                                     reply_markup=empty_keyboard())
                await message.answer(text='Мы в главном меню',
                                     reply_markup=standard_keyboard(user).as_markup())
                user.action = 'start_menu'

            else:
                await message.answer(text='Напиши мне свою учебную группу',
                                     reply_markup=empty_keyboard())
                user.action = 'registration_add_group'
        else:
            await message.answer(text='Не смог найти такого пользователя ВК. Ты точно правильно ввёл данные?')


async def add_group(bot: Bot, user: User, message: Message = None, callback: CallbackQuery = None,
                    partition: str = 'registration'):
    if callback:
        group = callback.data.replace(f'{partition}_add_group=', '').lower()

        if group in GROUPS:
            if not user.groups:
                user.groups = [group]
            else:
                if group not in user.groups:
                    user.groups.append(group)

            if partition == 'registration':
                name = user.VkFirstName if user.VkFirstName else user.TgName

                await message.answer(
                    f'Отлично, *{name}*! Я запомнил, что ты из группы *{user.groups[0]}*. Этот параметр '
                    f'можно будет изменить в настройках. Теперь я буду искать информацию для тебя персонально',
                    parse_mode='Markdown')
                await message.answer(text='Перехожу в главное меню',
                                     reply_markup=standard_keyboard(user).as_markup())
                user.action = 'start_menu'

            else:

                await callback.message.edit_text(f'Добавил в список групп {group}')
                user.action = f'{partition}_main'

            return True

        elif group == 'no_exist':
            await callback.message.edit_text(text='Я сообщил админу о возникшей проблеме. Как только появится '
                                                  'возможность, с тобой свяжутся')
            await bot.send_message(chat_id=756130127,
                                   text=f'Пользователь @{user.TgName} не может ввести группу. Он утверждает, что '
                                        f'нужной группы не существует')

    else:
        if message.text.lower() in GROUPS:
            if not user.groups:
                user.groups = [message.text.lower()]
            else:
                if message.text.lower() not in user.groups:
                    user.groups.append(message.text.lower())

            name = user.VkFirstName if user.VkFirstName else user.TgName

            if partition == 'registration':
                await message.answer(
                    f'Отлично, *{name}*! Я запомнил, что ты из группы *{user.groups[0]}*. Этот параметр '
                    f'можно будет изменить в настройках. Теперь я буду искать информацию для тебя персонально',
                    parse_mode='Markdown')

                if not user.VkID:
                    await message.answer(r'А ещё ты можешь зяглянуть в гости к [боту](vk\.me/sovet_phys) вк',
                                         parse_mode='MarkdownV2')

                await message.answer(
                    '*Полезный совет*\n\n'
                    r'Чтобы узнать, где находится кабинет, просто напиши мне его в любой форме, к примеру, _5\-47_, '
                    r'_547_, _5 47_, _столовая_ или даже _учебная часть_',
                    reply_markup=standard_keyboard(user).as_markup(),
                    parse_mode='MarkdownV2')
                user.action = 'start_menu'
            else:
                await message.answer(f'Добавил в список групп {message.text.lower()}')
                user.action = f'{partition}_main'

            return True

        elif message.text == 'Я не студент физфака':
            name = user.VkFirstName if user.VkFirstName else user.TgName
            await message.answer(f"Хорошо, {name}. Я запомнил, что ты не с физического "
                                 f"факультета. Пожалуйста, продублируй сообщение, чтобы мы его не "
                                 f"пропустили.\n\nP.s. Если кнопка была нажата по ошибке, ты всегда можешь "
                                 f"написать 'Я студент физфака' или 'Я студентка физфака', "
                                 f"чтобы зарегистрироваться.",
                                 reply_markup=empty_keyboard())
            user.action = 'not_student'

        else:
            await message.answer(
                r'Не могу найти группу. Я постарался подобрать похожие варианты на клавиатуре. Выбери один из них '
                r'или напиши ещё раз. Если попытки не увенчаются успехом, нажми на кнопку *Нет нужной группы*, '
                r'чтобы я подключил админа',
                reply_markup=groups_keyboard(main_part_callback=f'{partition}_add_group',
                                             groups=difflib.get_close_matches(message.text.lower(), GROUPS,
                                                                              n=4)).as_markup(),
                parse_mode='Markdown')
