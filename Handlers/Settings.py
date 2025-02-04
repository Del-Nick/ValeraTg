from datetime import datetime
import difflib
import re

from aiogram import Bot
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from Server.Core import DB
from Server.Models import User
from Scripts.ScheduleBuilder import schedule_builder
from Scripts.RequestsToVK import get_user_data_by_id
from Handlers.Keyboards import standard_keyboard, settings_keyboard, empty_keyboard, groups_keyboard, \
    groups_to_delete_keyboard, cancel_keyboard_usual
from Handlers.Registration import add_group
from Scripts.Arrays import GROUPS


def main_user_settings(user: User):
    answer = f'*Telegram ID*:         {user.TgID}\n'
    answer += f'*Учебная группа*:   {user.groups[0]}\n'

    if len(user.groups) > 1:
        answer += f'*Доп. группы*:      {", ".join(user.groups[1:])}\n\n'
    else:
        answer += '\n'

    answer += (f'Расписание на следующий день я присылаю тебе после '
               f'{user.settings.tomorrow_schedule_after.strftime("%H:%M")}')
    return answer


async def settings_handler(user: User, bot: Bot, message: Message = None, callback: CallbackQuery = None):
    if callback:
        if callback.data.startswith('settings_main'):
            await callback.message.edit_text(text=main_user_settings(user),
                                             reply_markup=settings_keyboard(user).as_markup(),
                                             parse_mode='Markdown')

        elif callback.data == 'settings_get_schedule_time':
            user.action = 'settings_get_schedule_time'

            try:
                await bot.edit_message_reply_markup(chat_id=callback.message.chat.id,
                                                    message_id=callback.message.message_id,
                                                    reply_markup=None)
            except TelegramBadRequest:
                pass

            await callback.message.answer(text='Введи время, после которого я буду присылать тебе расписание '
                                               'на следующий день, в формате ЧЧ:ММ',
                                          reply_markup=cancel_keyboard_usual())

        elif callback.data.startswith('settings_change_main_group'):
            if callback.data.startswith('settings_change_main_group='):
                group = callback.data.replace('settings_change_main_group=', '')

                if group in GROUPS:
                    user.groups = [message.text.lower()]
                    name = user.VkFirstName if user.VkFirstName else user.TgName

                    await message.answer(
                        f'Отлично, *{name}*! Я запомнил, что ты из группы *{user.groups[0]}*. Этот параметр '
                        f'можно будет изменить в настройках. Теперь я буду искать информацию для тебя персонально',
                        parse_mode='Markdown')
                    await message.answer(text=main_user_settings(user),
                                         reply_markup=settings_keyboard(user).as_markup())
                    user.action = 'settings_main'

                elif group == 'error':
                    await message.answer(
                        text='Я сообщил админу о возникшей проблеме. Как только появится возможность, '
                             'с тобой свяжутся')
                    await bot.send_message(chat_id=756130127,
                                           text=f'Пользователь @{user.TgName} не может ввести группу. Он '
                                                f'утверждает, что нужной группы не существует')

            elif user.settings.headman and not user.settings.admin:
                await callback.message.edit_text(text='Староста группы не может менять группу. Если группа была '
                                                      'изменена, напиши @DelNick, чтобы прекратить обладание '
                                                      'правами старосты',
                                                 reply_markup=settings_keyboard(user).as_markup())

            else:
                await callback.message.edit_text(text='Напиши номер группы, на которую хочешь поменять')
                user.action = 'settings_change_main_group'

        elif callback.data.startswith('settings_add_group'):
            if callback.data.startswith('settings_add_group='):
                if await add_group(bot=bot, user=user, callback=callback, partition='settings'):
                    await callback.message.answer(main_user_settings(user),
                                                  reply_markup=settings_keyboard(user).as_markup(),
                                                  parse_mode='Markdown')

            else:
                await callback.message.edit_text(text='Напиши номер группы, которую хочешь добавить')
                user.action = 'settings_add_group'

        elif callback.data.startswith('settings_delete_group'):
            if callback.data.startswith('settings_delete_group='):
                group = re.search(r'group=\d{3}[a-я]{0,3}', callback.data).group().replace('group=', '')
                user.groups.remove(group)
                await callback.message.edit_text(text=f'Группа {group} успешно удалена',
                                                 reply_markup=settings_keyboard(user).as_markup())

            elif len(user.groups) == 1:
                await callback.message.edit_text(text='У тебя указана только *учебная* группа. Ты можешь её '
                                                      'сменить, но удалить её нельзя',
                                                 reply_markup=settings_keyboard(user).as_markup(),
                                                 parse_mode='Markdown')
            elif len(user.groups) == 2:
                deleted_group = user.groups.pop(-1)
                await callback.message.edit_text(text=f'Группа {deleted_group} успешно удалена',
                                                 reply_markup=settings_keyboard(user).as_markup())

            else:
                await callback.message.edit_text(text='Выбери группу, которую хочешь удалить',
                                                 reply_markup=groups_to_delete_keyboard(
                                                     user.groups[1:]).as_markup())
                user.action = 'settings_delete_group'

        elif callback.data == 'settings_change_full_schedule':
            user.settings.full_schedule = not user.settings.full_schedule
            answer = main_user_settings(user)

            if user.settings.full_schedule:
                answer += '\n\nТеперь я буду выводить преподавателей при отправке расписания'
            else:
                answer += '\n\nБольше не буду выводить преподавателей при отправке расписания'

            await callback.message.edit_text(text=answer,
                                             reply_markup=settings_keyboard(user).as_markup(),
                                             parse_mode='Markdown')

        elif callback.data == 'settings_change_notifications':
            user.settings.notifications = not user.settings.notifications
            answer = main_user_settings(user)

            if user.settings.notifications:
                answer += '\n\nТеперь я буду присылать тебе уведомления о некоторых новостях и обновлениях'
            else:
                answer += '\n\nБольше не буду присылать тебе уведомления о новостях и обновлениях'

            await callback.message.edit_text(text=answer,
                                             reply_markup=settings_keyboard(user).as_markup(),
                                             parse_mode='Markdown')

        elif callback.data == 'settings_get_vk_id':
            user.action = 'settings_get_vk_id'
            await callback.message.edit_text(text='Напиши свой ID ВКонтакте или короткое имя')

        elif callback.data == 'start_menu':
            await callback.message.edit_text(text='Возвращаемся в главное меню',
                                             reply_markup=standard_keyboard(user).as_markup(),
                                             parse_mode='Markdown')
            user.action = 'start_menu'

    elif message:
        if 'settings_change_main_group' in user.action:
            if message.text.lower() in GROUPS:
                if message.text.lower() not in user.groups or len(user.groups) == 1:
                    user.groups[0] = message.text.lower()
                else:
                    user.groups[0] = user.groups.pop(user.groups.index(message.text.lower()))

                user.action = 'settings_get_schedule_time'
                await message.answer(
                    f'Отлично, *{user.TgName}*! Я запомнил, что ты из группы *{user.groups[0]}*. Этот параметр '
                    f'можно будет изменить в настройках. Теперь я буду искать информацию для тебя персонально',
                    reply_markup=empty_keyboard(),
                    parse_mode='Markdown')
                await message.answer(
                    text=main_user_settings(user),
                    reply_markup=settings_keyboard(user).as_markup(),
                    parse_mode='Markdown')

            else:
                if 'change_main_group_error' in user.action:
                    if 'alert_sent' not in user.action:
                        # TODO: добавить отправку alert
                        user.action = 'settings_change_main_group_error_alert_sent'
                        pass

                await message.answer(
                    f'Не могу найти группу. Выбери на клавиатуре, если найдёшь подходящую. Если попытки '
                    f'не увенчаются успехом, нажми на кнопку "Нет нужной группы", чтобы я подключил админа',
                    reply_markup=groups_keyboard(main_part_callback='settings_change_main_group',
                                                 groups=difflib.get_close_matches(message.text.lower(), GROUPS,
                                                                                  n=5)).as_markup())

                user.action = 'settings_change_main_group_error'

        elif 'settings_add_group' in user.action:
            if await add_group(bot=bot, user=user, message=message, partition='settings'):
                await message.answer(main_user_settings(user),
                                     reply_markup=settings_keyboard(user).as_markup(),
                                     parse_mode='Markdown')

        elif user.action == 'settings_get_vk_id':
            user_vk_data = await get_user_data_by_id(user, user_id=message.text.replace('@', ''))

            if user_vk_data:
                VkID, first_name, last_name, sex = user_vk_data

                if await DB.check_user_exists(VkID=VkID):
                    await DB.merge_records(user, VkID)
                    user = await DB.select_user(user.TgID)

                else:
                    user.VkID, user.VkFirstName, user.VkLastName, user.sex = VkID, first_name, last_name, sex

                await message.answer(text='Загрузил информацию из ВК',
                                     reply_markup=settings_keyboard(user).as_markup())
                user.action = 'settings_main'

            else:
                await message.answer(text='Ты точно правильно ввёл свой ник вк?')

        elif user.action == 'settings_get_schedule_time':
            if message.text == 'Отмена':
                user.action = 'settings_main'
                await message.answer('Возвращаюсь к меню настроек',
                                     reply_markup=empty_keyboard())
                await message.answer(text=main_user_settings(user),
                                     reply_markup=settings_keyboard(user).as_markup(),
                                     parse_mode='Markdown')

            else:
                try:
                    user.settings.tomorrow_schedule_after = datetime.strptime(message.text, '%H:%M').time()
                    user.action = 'settings_main'
                    await message.answer(f'Теперь я буду присылать расписание на следующий день после '
                                         f'{user.settings.tomorrow_schedule_after.strftime('%H:%M')}',
                                         reply_markup=empty_keyboard())
                    await message.answer(text=main_user_settings(user),
                                         reply_markup=settings_keyboard(user).as_markup(),
                                         parse_mode='Markdown')

                except ValueError:
                    await message.answer(text='Проверь правильность ввода. Помни, что для меня важен формат ЧЧ:ММ',
                                         reply_markup=cancel_keyboard_usual())
