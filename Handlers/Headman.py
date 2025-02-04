import asyncio
import json
import os
import re
from datetime import datetime
from io import BytesIO
from queue import Queue
from tokenize import group

import aiogram
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (Message, CallbackQuery, InlineKeyboardButton, InputMediaDocument, InputMediaPhoto)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from prettytable import PrettyTable, ALL

from Handlers.Keyboards import standard_keyboard, custom_keyboard
from Scripts.Others import remove_inline_keyboard
from Scripts.RequestsToVK import get_vk_attachment
from Scripts.ScheduleBuilder import weekdays
from Server.Core import HomeworksDB
from Server.Models import User, Homeworks

queue_homeworks: Queue = Queue()
file_senders: set[tuple] = set()


class Keyboards:
    @staticmethod
    def main_headman_keyboards():
        keyboard = InlineKeyboardBuilder()

        keyboard.row(InlineKeyboardButton(text='Редактировать учебники', callback_data='headman_edit_books'))
        keyboard.row(InlineKeyboardButton(text='Редактировать ДЗ', callback_data='headman_hwks_main'))
        keyboard.row(InlineKeyboardButton(text='Редактировать напоминания',
                                          callback_data='headman_edit_notifications'))
        keyboard.row(InlineKeyboardButton(text='Редактировать расписание',
                                          callback_data='headman_schedule'))
        keyboard.row(InlineKeyboardButton(text='Назад', callback_data='start_menu'))

        return keyboard

    @staticmethod
    def edit_homeworks_subjects_keyboard(homeworks: Homeworks = None):
        keyboard = InlineKeyboardBuilder()

        if homeworks.homeworks:
            for num, subject in enumerate(homeworks.homeworks.keys()):
                keyboard.button(text=subject,
                                callback_data=f'headman_hwks_edit_subj={subject}_main')

            keyboard.adjust(2)

        add_subject = InlineKeyboardButton(text='Добавить предмет',
                                           callback_data=f'headman_hwks_add_subj')
        delete_subject = InlineKeyboardButton(text='Удалить предмет',
                                              callback_data=f'headman_hwks_dlt_subj')

        keyboard.row(add_subject, delete_subject) if homeworks.homeworks \
            else keyboard.row(add_subject)

        keyboard.row(InlineKeyboardButton(text='Назад', callback_data='headman_main'))

        return keyboard

    @staticmethod
    def delete_subject_keyboard(homeworks: Homeworks = None):
        keyboard = InlineKeyboardBuilder()

        if homeworks.homeworks:
            for num, subject in enumerate(homeworks.homeworks.keys()):
                keyboard.button(text=subject,
                                callback_data=f'headman_hwks_dlt_subj={subject}')

            keyboard.adjust(2)

        keyboard.row(InlineKeyboardButton(text='Назад', callback_data='headman_hwks_main'))

        return keyboard

    @staticmethod
    def cancel_keyboard():
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text='Отмена', callback_data='headman_hwks_main'))
        return keyboard

    @staticmethod
    def yes_no_delete_subject(subject: str):
        keyboard = InlineKeyboardBuilder()
        no = InlineKeyboardButton(text='❌ Нет', callback_data='headman_hwks_main')
        yes = InlineKeyboardButton(text='✅️ Да',
                                   callback_data=f'headman_hwks_allwd_dlt_subj={subject}')
        keyboard.row(yes, no)
        return keyboard


kb = Keyboards()


async def headman_handler(bot: Bot, user: User, message: Message = None, callback: CallbackQuery = None):
    if callback:
        if callback.data == 'headman_main':
            if user.settings.headman:
                await callback.message.edit_text(text='Ты главном меню старосты',
                                                 reply_markup=kb.main_headman_keyboards().as_markup())

            else:
                await callback.message.edit_text(text='У тебя нет прав на просмотр этой страницы',
                                                 reply_markup=standard_keyboard(user).as_markup())

        elif callback.data.startswith('headman_hwks'):
            await edit_homeworks_subjects(bot=bot, user=user, callback=callback)

        elif callback.data.startswith('headman_schedule'):
            await edit_custom_schedule(bot=bot, user=user, callback=callback)

    else:
        if user.action.startswith('headman_hwks'):
            await edit_homeworks_subjects(bot=bot, user=user, message=message)

        elif callback.data.startswith('headman_schedule'):
            await edit_custom_schedule(bot=bot, user=user, message=message)


def get_prettytable_with_schedule(group: str, day: str, custom_schedule: dict, schedule: dict,
                                  lesson: str = None, parity: str = None) -> PrettyTable:
    try:
        lesson_data = custom_schedule[group][day]
    except KeyError:
        try:
            lesson_data = schedule[group][day]
        except KeyError:
            return None

    if parity:
        table = PrettyTable(hrules=ALL)
        table.field_names = ['Предмет', 'Преп', 'Каб']
        table._max_width = {"Предмет": 10, 'Преп': 10, "Каб.": 4}

        if lesson in lesson_data.keys():
            lesson_data = lesson_data[lesson]
        else:
            return None

        if parity == 'odd' or parity == 'even':
            row = [lesson_data[parity]["lesson"], lesson_data[parity]["teacher"], lesson_data[parity]["room"]]
            for i, x in enumerate(row):
                if x is None:
                    row[i] = ''

            table.add_row(row)

        else:
            for _ in ['odd', 'even']:
                row = [lesson_data[_]["lesson"], lesson_data[_]["teacher"], lesson_data[_]["room"]]

                for i, x in enumerate(row):
                    if x is None:
                        row[i] = ''

                table.add_row(row)

        return table

    elif lesson:
        table = PrettyTable(hrules=ALL)
        table.field_names = ['Предмет', 'Преп', 'Каб']
        table._max_width = {"Предмет": 10, 'Преп': 10, "Каб.": 4}

        if lesson in lesson_data.keys():
            lesson_data = lesson_data[lesson]
        else:
            return None

        for _ in ['odd', 'even']:
            row = [lesson_data[_]["lesson"], lesson_data[_]["teacher"], lesson_data[_]["room"]]

            for i, x in enumerate(row):
                if x is None:
                    row[i] = ''

            table.add_row(row)

        return table

    else:
        table = PrettyTable(hrules=ALL)
        table.field_names = ['№', 'Предмет', 'Преп', 'Каб']
        table._max_width = {'№': 2, "Предмет": 10, 'Преп': 8, "Каб.": 4}

        for lesson in range(1, 7):
            for _ in ['odd', 'even']:
                row = [lesson,
                       lesson_data[str(lesson)][_]["lesson"],
                       lesson_data[str(lesson)][_]["teacher"],
                       lesson_data[str(lesson)][_]["room"]]

                for i, x in enumerate(row):
                    if x is None:
                        row[i] = ''

                table.add_row(row)

        return table


async def edit_custom_schedule(bot: Bot, user: User, message: Message = None, callback: CallbackQuery = None):
    custom_schedule_path = 'Files/Custom Schedule.json'
    if not os.path.exists(custom_schedule_path):
        custom_schedule = {}
        with open(custom_schedule_path, 'w+', encoding='utf-8') as f:
            json.dump(custom_schedule, f, ensure_ascii=False)

    else:
        with open(custom_schedule_path, 'r', encoding='utf-8') as f:
            custom_schedule = json.load(f)

    if os.path.exists('Files/Schedule.json'):
        with open('Files/Schedule.json', 'r', encoding='utf-8') as f:
            schedule = json.load(f)

        if callback:
            if 'day' not in callback.data:
                buttons = [(day, f'day={i}') for i, day in enumerate(weekdays)]

                await callback.message.edit_text('Выбери день недели для редактирования',
                                                 reply_markup=custom_keyboard(callback_back_button='headman_main',
                                                                              main_callback='headman_schedule',
                                                                              buttons=buttons,
                                                                              buttons_in_row=3).as_markup())

            elif 'lesson' not in callback.data:
                day = int(re.search(r'day=\d', callback.data).group().replace('day=', ''))
                buttons = [(str(lesson), f'lesson={lesson}') for lesson in range(1, 7)]

                table = get_prettytable_with_schedule(group=user.groups[0], day=weekdays[day],
                                                      schedule=schedule, custom_schedule=custom_schedule)

                await callback.message.edit_text(f'{weekdays[day].upper()}\n'
                                                 f'```\n{table}```\n'
                                                 f'Выбери номер пары для редактирования',
                                                 reply_markup=custom_keyboard(callback_back_button=f'headman_schedule',
                                                                              main_callback=f'headman_schedule_day={day}',
                                                                              buttons=buttons,
                                                                              buttons_in_row=6).as_markup(),
                                                 parse_mode='MarkdownV2')

            elif 'parity' not in callback.data:
                day = int(re.search(r'day=\d', callback.data).group().replace('day=', ''))
                lesson = re.search(r'lesson=\d', callback.data).group().replace('lesson=', '')

                buttons = [('Чётная неделя', 'parity=even'),
                           ('Нечётная неделя', 'parity=odd'),
                           ('Нечередующаяся пара', 'parity=o+e')]

                table = get_prettytable_with_schedule(group=user.groups[0], day=weekdays[day],
                                                      schedule=schedule, custom_schedule=custom_schedule,
                                                      lesson=lesson)
                if not table:
                    user.action = 'start'
                    await callback.message.edit_text('Я не смог найти расписания для твоей группы. '
                                                     'Свяжись с разработчиками',
                                                     reply_markup=standard_keyboard(user).as_markup())
                    return

                await callback.message.edit_text(f'{weekdays[day].upper()}, {lesson} ПАРА:\n'
                                                 f'```\n{table}```\n\n'
                                                 f'Выбери чётность недели для редактирования',
                                                 reply_markup=custom_keyboard(
                                                     callback_back_button=f'headman_schedule_day={day}',
                                                     main_callback=f'headman_schedule_day={day}_lesson={lesson}',
                                                     buttons=buttons,
                                                     buttons_in_row=2).as_markup(),
                                                 parse_mode='MarkdownV2')

            elif 'mode' not in callback.data:
                day = int(re.search(r'day=\d', callback.data).group().replace('day=', ''))
                lesson = re.search(r'lesson=\d', callback.data).group().replace('lesson=', '')
                parity = re.search(r'parity=[a-zA-Z+]{3,4}', callback.data).group().replace('parity=', '')

                table = get_prettytable_with_schedule(group=user.groups[0], day=weekdays[day],
                                                      schedule=schedule, custom_schedule=custom_schedule,
                                                      lesson=lesson, parity=parity)

                buttons = [('Название', 'title'),
                           ('Преподаватель', 'teacher'),
                           ('Кабинет', 'room'),
                           ('Всё целиком', 'all')]

                await callback.message.edit_text(f'{weekdays[day].upper()}, {lesson} ПАРА:\n'
                                                 f'```\n{table}```\n\n'
                                                 f'Выбери, что именно будешь менять',
                                                 reply_markup=custom_keyboard(
                                                     callback_back_button=f'headman_schedule_day={day}_lesson={lesson}',
                                                     buttons=buttons,
                                                     main_callback=f'headman_schedule_day={day}_lesson={lesson}_parity={parity}',
                                                     buttons_in_row=2).as_markup(),
                                                 parse_mode='MarkdownV2')

            else:
                day = int(re.search(r'day=\d', callback.data).group().replace('day=', ''))
                lesson = re.search(r'lesson=\d', callback.data).group().replace('lesson=', '')
                parity = re.search(r'parity=[a-zA-Z+]{3,4}', callback.data).group().replace('parity=', '')
                mode = re.search(r'mode=[a-zA-Z+]{3,7}', callback.data).group().replace('mode=', '')

                table = get_prettytable_with_schedule(group=user.groups[0], day=weekdays[day],
                                                      schedule=schedule, custom_schedule=custom_schedule,
                                                      lesson=lesson, parity=parity)

                user.action = f'headman_schedule_day={day}_lesson={lesson}_parity={parity}_mode={mode}'

                match mode:
                    case 'title':
                        await callback.message.edit_text(f'{weekdays[day].upper()}, {lesson} ПАРА:\n'
                                                         f'```\n{table}```\n\n'
                                                         f'Введи другое название предмета',
                                                         reply_markup=custom_keyboard(
                                                             callback_back_button=f'headman_schedule_day={day}_lesson={lesson}_parity={parity}',
                                                             main_callback=f'headman_schedule_day={day}_lesson={lesson}_parity={parity}_mode={mode}',
                                                             buttons_in_row=2).as_markup(),
                                                         parse_mode='MarkdownV2')

                    case 'teacher':
                        await callback.message.edit_text(f'{weekdays[day].upper()}, {lesson} ПАРА:\n'
                                                         f'```\n{table}```\n\n'
                                                         f'Введи имя преподавателя',
                                                         reply_markup=custom_keyboard(
                                                             callback_back_button=f'headman_schedule_day={day}_lesson={lesson}_parity={parity}',
                                                             main_callback=f'headman_schedule_day={day}_lesson={lesson}_parity={parity}_mode={mode}',
                                                             buttons_in_row=2).as_markup(),
                                                         parse_mode='MarkdownV2')

                    case 'room':
                        await callback.message.edit_text(f'{weekdays[day].upper()}, {lesson} ПАРА:\n'
                                                         f'```\n{table}```\n\n'
                                                         f'Введи номер кабинета',
                                                         reply_markup=custom_keyboard(
                                                             callback_back_button=f'headman_schedule_day={day}_lesson={lesson}_parity={parity}',
                                                             main_callback=f'headman_schedule_day={day}_lesson={lesson}_parity={parity}_mode={mode}',
                                                             buttons_in_row=2).as_markup(),
                                                         parse_mode='MarkdownV2')

                    case 'all':
                        await callback.message.edit_text(f'{weekdays[day].upper()}, {lesson} ПАРА:\n'
                                                         f'```\n{table}```\n\n'
                                                         f'Введи новую пару по образцу:\n\n'
                                                         f'*Название пары*\n'
                                                         f'*Преподаватель*\n'
                                                         f'*Номер набинета*\n\n'
                                                         f'Для меня очень важны переходы на новую строку, не забывай об этом\\. '
                                                         f'Если преподаватель или кабинет неизвестны, оставь пустую строку',
                                                         reply_markup=custom_keyboard(
                                                             callback_back_button=f'headman_schedule_day={day}_lesson={lesson}_parity={parity}',
                                                             main_callback=f'headman_schedule_day={day}_lesson={lesson}_parity={parity}_mode={mode}',
                                                             buttons_in_row=2).as_markup(),
                                                         parse_mode='MarkdownV2')

        else:
            if all([x in user.action for x in ['title', 'teacher', 'room', 'all']]):
                day = int(re.search(r'day=\d', callback.data).group().replace('day=', ''))
                lesson = re.search(r'lesson=\d', callback.data).group().replace('lesson=', '')
                parity = re.search(r'parity=[a-zA-Z+]{3,4}', callback.data).group().replace('parity=', '')
                mode = re.search(r'mode=[a-zA-Z+]{3,7}', callback.data).group().replace('mode=', '')

                with open('../../Valera/Files/Schedule.json', 'r', encoding='utf-8') as f:
                    custom_schedule = json.load(f)

                user.action = 'headman_main'

                if user.groups[0] not in custom_schedule.keys():
                    custom_schedule[user.groups[0]] = {weekdays[day]:
                        {lesson: {
                            'even': {'lesson': '', 'room': '', 'teacher': ''},
                            'odd': {'lesson': '', 'room': '', 'teacher': ''}}}}

                match mode:
                    case 'title':
                        custom_schedule[user.groups[0]][weekdays[day]][lesson][parity]['lesson'] = message.text

                        table = get_prettytable_with_schedule(group=user.groups[0], day=weekdays[day],
                                                              schedule=schedule, custom_schedule=custom_schedule)

                        await message.answer(f'{weekdays[day].upper()}:\n'
                                             f'```\n{table}```\n\n'
                                             f'Отлично! Я запомнил новое название предмета',
                                             reply_markup=kb.main_headman_keyboards().as_markup())

                    case 'teacher':
                        custom_schedule[user.groups[0]][weekdays[day]][lesson][parity]['teacher'] = message.text

                        table = get_prettytable_with_schedule(group=user.groups[0], day=weekdays[day],
                                                              schedule=schedule, custom_schedule=custom_schedule)

                        await message.answer(f'{weekdays[day].upper()}:\n'
                                             f'```\n{table}```\n\n'
                                             f'Отлично! Я запомнил новое название предмета',
                                             reply_markup=kb.main_headman_keyboards().as_markup())


async def edit_homeworks_subjects(bot: Bot, user: User, message: Message = None, callback: CallbackQuery = None):
    homeworks = await HomeworksDB.select_homeworks(user.groups[0])

    if callback:
        if callback.data == 'headman_hwks_main':
            if homeworks.homeworks:
                await callback.message.edit_text(text='Выбери предмет для редактирования домашних заданий',
                                                 reply_markup=kb.edit_homeworks_subjects_keyboard(
                                                     homeworks).as_markup())
            else:
                await callback.message.edit_text(text='У тебя пока нет предметов',
                                                 reply_markup=kb.edit_homeworks_subjects_keyboard(
                                                     homeworks).as_markup())

        elif callback.data == 'headman_hwks_add_subj':
            user.action = 'headman_hwks_add_subj'
            await callback.message.edit_text(text='Напиши название предмета, который хочешь добавить. Название не '
                                                  'должно превышать 15 символов',
                                             reply_markup=kb.cancel_keyboard().as_markup())

        elif callback.data == 'headman_hwks_delete_subj':
            if len(homeworks.homeworks.keys()) > 1:
                await callback.message.edit_text(text='Выбери предмет, который нужно удалить',
                                                 reply_markup=kb.delete_subject_keyboard(homeworks).as_markup())

            else:
                subject = list(homeworks.homeworks.keys())[0]
                await callback.message.edit_text(text=f'Предмет *{subject}* и все домашние задания по нему будут '
                                                      f'удалены. Ты уверен?',
                                                 reply_markup=kb.yes_no_delete_subject(subject).as_markup(),
                                                 parse_mode='Markdown')

        elif callback.data.startswith('headman_hwks_edit_subj'):
            await edit_homework_by_subject(bot=bot, user=user, callback=callback, homeworks=homeworks)

        elif callback.data == 'headman_hwks_dlt_subj':
            await callback.message.edit_text(text='Выбери предмет, который нужно удалить',
                                             reply_markup=kb.delete_subject_keyboard(homeworks).as_markup())

        elif callback.data.startswith('headman_hwks_dlt_subj='):
            subject = callback.data.replace('headman_hwks_dlt_subj=', '')
            await callback.message.edit_text(text=f'Предмет *{subject}* и все домашние задания по нему будут '
                                                  f'удалены. Ты уверен?',
                                             reply_markup=kb.yes_no_delete_subject(subject).as_markup(),
                                             parse_mode='Markdown')

        elif callback.data.startswith('headman_hwks_allwd_dlt_subj'):
            subject = callback.data.replace('headman_hwks_allwd_dlt_subj=', '')
            del homeworks.homeworks[subject]
            await callback.message.edit_text(text=f'Предмет *{subject}* успешно удалён',
                                             reply_markup=kb.edit_homeworks_subjects_keyboard(homeworks).as_markup(),
                                             parse_mode='Markdown')

        await HomeworksDB.update_homeworks(homeworks)

    else:
        if user.action == 'headman_hwks_add_subj':
            if len(message.text) <= 15:
                user.action = 'headman_edit_homeworks_main'

                if homeworks.homeworks:
                    homeworks.homeworks[message.text] = []
                else:
                    homeworks.homeworks = {message.text: []}

                await message.answer(text=f'Предмет *{message.text}* успешно добавлен',
                                     reply_markup=kb.edit_homeworks_subjects_keyboard(homeworks).as_markup(),
                                     parse_mode='Markdown')

                await HomeworksDB.update_homeworks(homeworks)

            else:
                await message.answer(text=f'В названии *{message.text}* количество символов равно {len(message.text)}. '
                                          f'Сократи и пришли мне его заново. К примеру, _Матанализ_ воспринимается '
                                          f'проще, чем _Математический анализ_',
                                     reply_markup=kb.cancel_keyboard().as_markup(),
                                     parse_mode='Markdown')

        elif user.action.startswith('headman_hwks_edit_subj'):
            await edit_homework_by_subject(bot=bot, user=user, message=message, homeworks=homeworks)


async def edit_homework_by_subject(bot: Bot, user: User, homeworks: Homeworks,
                                   message: Message = None, callback: CallbackQuery = None):
    chat_id = callback.message.chat.id if callback else message.chat.id

    if callback:
        subject = re.search(r'subj=[0-9a-zA-Zа-яА-Я ]{1,15}', callback.data).group().replace('subj=', '')

        can_edit_message = True

        if 'main' in callback.data:
            user.action = f'headman_hwks_edit_subj={subject}_main'
            if homeworks.homeworks[subject]:
                for i, homework in enumerate(homeworks.homeworks[subject]):

                    docs = []
                    photos = []

                    for attach in homework['attachments']:
                        if attach['type'] == 'doc':
                            docs.append((InputMediaDocument(media=attach['tg_file_id']), attach['tg_file_id']))

                        else:
                            photos.append((InputMediaPhoto(media=attach['tg_file_id']), attach['tg_file_id']))

                    if homework['text']:
                        if i == 0:
                            await callback.message.edit_reply_markup(reply_markup=None)
                            await callback.message.edit_text(text=f'{i + 1}. {homework['text']}\n\n'
                                                                  f'Дата добавления: {homework['date']}')
                            can_edit_message = False

                        else:
                            await callback.message.answer(text=f'{i + 1}. {homework['text']}\n\n'
                                                               f'Дата добавления: {homework['date']}')

                    else:
                        await callback.message.answer(text=f'{i + 1}. Без описания\n\n'
                                                           f'Дата добавления: {homework['date']}')

                    try:
                        if len(docs) == 1:
                            await bot.send_document(chat_id=callback.message.chat.id, document=docs[0][1])
                        elif len(docs) > 1:
                            await bot.send_media_group(chat_id=callback.message.chat.id, media=[doc[0] for doc in docs])
                    except:
                        await callback.message.answer(text='Не удалось загрузить вложение')

                    try:
                        if len(photos) == 1:
                            await bot.send_photo(chat_id=callback.message.chat.id, photo=photos[0][1])
                        elif len(photos) > 1:
                            await bot.send_media_group(chat_id=callback.message.chat.id,
                                                       media=[photo[0] for photo in photos])
                    except:
                        await callback.message.answer(text='Не удалось загрузить вложение')

            if len(homeworks.homeworks[subject]) > 0:
                buttons = [('Добавить ДЗ', f'edit_subj={subject}_add'), ('Удалить ДЗ', f'edit_subj={subject}_dlt')]
            else:
                buttons = [('Добавить ДЗ', f'edit_subj={subject}_add')]

            if can_edit_message:
                await callback.message.edit_text('Выбери действие',
                                                 reply_markup=custom_keyboard(main_callback='headman_hwks',
                                                                              callback_back_button='headman_hwks_main',
                                                                              buttons=buttons).as_markup())
            else:
                await callback.message.answer('Выбери действие',
                                              reply_markup=custom_keyboard(main_callback='headman_hwks',
                                                                           callback_back_button='headman_hwks_main',
                                                                           buttons=buttons).as_markup())

        elif 'add' in callback.data:
            user.action = f'headman_hwks_edit_subj={subject}_add'
            await callback.message.edit_text('Пришли мне текст домашнего задания и файлы, которые нужно '
                                             'прикрепить\n\n'
                                             'P.s. Размер файла не должен превышать 20 Мб\n'
                                             'P.p.s. Дождись подтверждения загрузки (примерно 10 секунд)',
                                             reply_markup=custom_keyboard(callback_back_button='headman_hwks_main')
                                             .as_markup())

        elif 'dlt' in callback.data:
            if 'dlt_' not in callback.data:
                user.action = f'headman_hwks_edit_subj={subject}_delete'

                if len(homeworks.homeworks[subject]) > 1:
                    buttons = [(str(x + 1), f'edit_subj={subject}_dlt_{x + 1}') for x in
                               range(len(homeworks.homeworks[subject]))]
                    await callback.message.edit_text('Выбери номер домашнего задания, которое нужно удалить',
                                                     reply_markup=custom_keyboard(main_callback='headman_hwks',
                                                                                  callback_back_button='headman_hwks_main',
                                                                                  buttons=buttons,
                                                                                  buttons_in_row=5).as_markup())

                elif len(homeworks.homeworks[subject]) == 1:
                    homeworks.homeworks[subject] = []
                    buttons = [('Добавить ДЗ', f'edit_subj={subject}_add')]
                    await callback.message.edit_text('По предмету больше нет домашних заданий',
                                                     reply_markup=custom_keyboard(main_callback='headman_hwks',
                                                                                  callback_back_button='headman_hwks_main',
                                                                                  buttons=buttons).as_markup())

            else:
                await remove_inline_keyboard(bot, callback.message)
                num = re.search(r'dlt_\d{1,3}', callback.data).group().replace('dlt_', '')
                num = int(num) - 1

                homeworks.homeworks[subject].pop(num)

                if homeworks.homeworks[subject]:
                    for i, homework in enumerate(homeworks.homeworks[subject]):
                        docs = []
                        photos = []
                        await bot.send_message(chat_id=chat_id, text=f'{i + 1}. {homework['text']}')
                        try:
                            for attach in homework['attachments']:
                                if attach['type'] == 'doc':
                                    docs.append(InputMediaDocument(media=attach['tg_file_id']))

                                elif attach['type'] == 'photo':
                                    photos.append(InputMediaPhoto(media=attach['tg_file_id']))

                            if docs:
                                await bot.send_media_group(chat_id=chat_id, media=docs)
                            elif photos:
                                await bot.send_media_group(chat_id=chat_id, media=photos)

                        except TelegramBadRequest:
                            await callback.message.answer('Вложение было загружено с ошибкой и не может быть '
                                                          'отправлено')

                buttons = [('Добавить ДЗ', f'edit_subj={subject}_add'), ('Удалить ДЗ', f'edit_subj={subject}_dlt')]
                await callback.message.answer('Выбери действие',
                                              reply_markup=custom_keyboard(main_callback='headman_hwks',
                                                                           callback_back_button='headman_hwks_main',
                                                                           buttons=buttons).as_markup())

    else:
        subject = re.search(r'subj=[0-9a-zA-Zа-яА-Я ]{1,15}', user.action).group().replace('subj=', '')

        if 'add' in user.action:
            tg_file_id = None
            vk_file_id = None

            if message.document:
                media_type = 'doc'
                tg_file_id = message.document.file_id
            elif message.photo:
                media_type = 'photo'
                tg_file_id = message.photo[-1].file_id
            else:
                media_type = None

            if media_type:
                data = BytesIO()

                try:
                    if media_type == 'doc':
                        await bot.download(message.document.file_id, data)
                        vk_file_id = await get_vk_attachment(data=data,
                                                             filename=message.document.file_name,
                                                             type=media_type)

                    elif media_type == 'photo':
                        await bot.download(message.photo[-1].file_id, data)
                        vk_file_id = await get_vk_attachment(data=data,
                                                             filename=message.photo[-1].file_unique_id + '.jpg',
                                                             type=media_type)

                except aiogram.exceptions.TelegramBadRequest:
                    pass

            date = datetime.now()

            if message.text:
                queue_homeworks.put({'text': message.text,
                                     'date': date})

            elif message.caption:
                queue_homeworks.put({'text': message.caption,
                                     'attachments': {'tg_file_id': tg_file_id,
                                                     'vk_file_id': vk_file_id,
                                                     'type': media_type},
                                     'date': date})
            else:
                queue_homeworks.put({'attachments': {'tg_file_id': tg_file_id,
                                                     'vk_file_id': vk_file_id,
                                                     'type': media_type},
                                     'date': date})

            await manager_files_saving(message=message, user=user, subject=subject)


async def remove_user_from_file_senders(message: Message, user: User, subject: str):
    await asyncio.sleep(10)

    await update_homeworks(message=message, user=user, subject=subject)
    file_senders.remove((message.from_user.id, subject))


async def update_homeworks(message: Message, user: User, subject: str):
    homeworks = await HomeworksDB.select_homeworks(group=user.groups[0])

    homework = {'text': '',
                'attachments': [],
                'date': datetime.now().strftime('%d.%m.%Y %H:%M')}

    for _ in range(queue_homeworks.qsize()):
        temp = queue_homeworks.get()
        if 'text' in temp.keys():
            homework['text'] = temp['text']

        if 'attachments' in temp.keys():
            homework['attachments'].append(temp['attachments'])

    homeworks.homeworks[subject].append(homework)

    await HomeworksDB.update_homeworks(homeworks)

    buttons = [('Добавить ДЗ', f'edit_subj={subject}_add'), ('Удалить ДЗ', f'edit_subj={subject}_dlt')]
    await message.answer('Сохранил домашнее задание',
                         reply_markup=custom_keyboard(main_callback='headman_hwks',
                                                      callback_back_button='headman_hwks_main',
                                                      buttons=buttons).as_markup())


async def manager_files_saving(message: Message, user: User, subject: str):
    if (message.from_user.id, subject) in file_senders:
        return

    file_senders.add((message.from_user.id, subject))
    await remove_user_from_file_senders(message=message, subject=subject, user=user)
