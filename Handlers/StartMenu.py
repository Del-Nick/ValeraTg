import re
from datetime import datetime, timedelta
from pprint import pprint

import aiogram.exceptions
from natsort import natsorted

from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InputMediaDocument, InputMediaPhoto
from aiogram.exceptions import TelegramBadRequest

from Admin.Admin import admin_handler
from Scripts.FloorCabinetSearchEngine import check_rooms, rooms
from Scripts.Others import remove_inline_keyboard, escape_markdown
from Server.Core import DB, BooksDB, HomeworksDB, WorkshopsDB, SessionDB
from Server.Models import User, Books, Workshops
from Scripts.ScheduleBuilder import schedule_builder
from Scripts.Arrays import GROUPS, workshop_rooms
from Handlers.Headman import headman_handler
from Handlers.Keyboards import standard_keyboard, settings_keyboard, custom_keyboard, empty_keyboard
from prettytable import PrettyTable, ALL


async def back_to_start(user: User, message: Message, bot: Bot):
    if user.groups:
        user.action = 'start_menu'
        await message.answer('Любовь, надежда и вера-а-а', reply_markup=standard_keyboard(user).as_markup())

        try:
            await bot.edit_message_reply_markup(chat_id=message.chat.id,
                                                message_id=message.message_id - 1,
                                                reply_markup=None)
        except TelegramBadRequest:
            pass

    elif not user.groups:
        await message.answer('Для работы мне необходимо знать твою группу. Подожди немного, '
                             'скоро мы со всем разберёмся', reply_markup=standard_keyboard(user).as_markup())


async def start_menu(bot: Bot, user: User, message: Message = None, callback: CallbackQuery = None):
    if callback:
        if callback.data.startswith('start_homeworks'):
            await get_and_send_homeworks(bot=bot, user=user, callback=callback)

        elif callback.data.startswith('start_books'):
            await get_and_send_books(bot, user, callback)

        elif callback.data.startswith('start_workshops'):
            await get_and_send_workshops(bot, user, callback)

        elif callback.data == 'start_schedule_get_custom_group':
            user.action = 'start_schedule_get_custom_group'
            await callback.message.edit_text(text='Введи группу, для которой необходимо узнать расписание')

        elif callback.data.startswith('start_schedule'):
            user.action = 'start_schedule'
            await schedule_builder(bot=bot, user=user, callback=callback)

        elif callback.data.startswith('start_session'):
            try:
                await bot.delete_message(chat_id=callback.message.chat.id,
                                         message_id=callback.message.message_id)
            except aiogram.exceptions.TelegramBadRequest:
                pass

            await callback.message.answer_animation(
                'CAACAgIAAxkBAAENqbFnmlcOX1gwkPqabl0qH9iPSFxjcwAClAAD9wLID6LmvuevDazoNgQ')
            await callback.message.answer(text='Поздравляем тебя с окончанием сессии! Наконец-то чиииллл...',
                                          reply_markup=standard_keyboard(user).as_markup())

        elif callback.data == 'settings_main':
            user.action = 'settings_main'
            answer = f'*Telegram ID*:           {user.TgID}\n'
            answer += f'*Учебная группа*:       {user.groups[0]}\n'
            answer += f'*Доп. группы*:          {", ".join(user.groups[1:])}\n\n' if len(user.groups) > 1 else '\n'
            answer += (f'Расписание на следующий день я присылаю тебе после '
                       f'{user.settings.tomorrow_schedule_after.strftime("%H:%M")}')
            await callback.message.edit_text(text=answer,
                                             reply_markup=settings_keyboard(user).as_markup(),
                                             parse_mode='Markdown')

        elif callback.data == 'start_admin':
            user.action = 'admin'
            user = await admin_handler(user, message, callback)

        elif callback.data == 'start_get_error':
            user.action = 'start_get_error'
            await callback.message.edit_text('Подробно опиши ошибку, чтобы мы как можно скорее её исправили',
                                             reply_markup=custom_keyboard(
                                                 callback_back_button='start_schedule').as_markup())

        elif callback.data == 'start_menu':
            user.action = 'start_menu'
            await callback.message.edit_text(text='Возращаемся в главное меню',
                                             reply_markup=standard_keyboard(user).as_markup())

    elif message:
        if user.action == 'start_schedule_get_custom_group':
            if message.text.lower() in GROUPS:
                user.action = f'start_schedule_group={message.text.lower()}'
                await schedule_builder(bot=bot, user=user, message=message, group=message.text.lower())

            else:
                await message.answer("Не могу найти такую группу",
                                     reply_markup=empty_keyboard())

        elif user.action == 'start_get_error':
            await bot.send_message(chat_id=756130127,
                                   text=f'Пользователь @{user.TgName} из группы {user.groups[0]} нашёл ошибку:\n\n'
                                        f'{message.text}')
            await message.answer('Я сообщил об ошибке админу. Спасибо за бдительность!',
                                 reply_markup=standard_keyboard(user).as_markup())

        elif check_rooms(message):
            await remove_inline_keyboard(bot, message)
            await rooms(user, message)


async def get_and_send_homeworks(bot: Bot, user: User, callback: CallbackQuery):
    homeworks = await HomeworksDB.select_homeworks(user.groups[0])

    if 'subj' in callback.data:
        subject = re.search(r'subj=.{1,15}', callback.data).group().replace('subj=', '')
        await remove_inline_keyboard(bot, callback.message)

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
                    print(f'*{i + 1}\\.*      {escape_markdown(homework['text'])}\n\n'
                          f'_Дата добавления: {homework['date']}_')
                    if i == 0:
                        await callback.message.edit_text(
                            text=f'*{i + 1}\\.*      {escape_markdown(homework['text'])}\n\n'
                                 f'_Дата добавления: {escape_markdown(homework['date'])}_',
                            parse_mode='MarkdownV2')

                    else:
                        await callback.message.answer(text=f'*{i + 1}\\.*     {escape_markdown(homework['text'])}\n\n'
                                                           f'_Дата добавления: {escape_markdown(homework['date'])}_',
                                                      parse_mode='MarkdownV2')

                else:
                    await callback.message.answer(text=f'*{i + 1}\\.* Без описания\n\n'
                                                       f'_Дата добавления: {escape_markdown(homework['date'])}_',
                                                  parse_mode='MarkdownV2')

                if len(docs) == 1:
                    await bot.send_document(chat_id=callback.message.chat.id, document=docs[0][1])
                elif len(docs) > 1:
                    await bot.send_media_group(chat_id=callback.message.chat.id, media=[doc[0] for doc in docs])

                if len(photos) == 1:
                    await bot.send_photo(chat_id=callback.message.chat.id, photo=photos[0][1])
                elif len(photos) > 1:
                    await bot.send_media_group(chat_id=callback.message.chat.id, media=[photo[0] for photo in photos])

            buttons = [(x, f'subj={x}') for x in homeworks.homeworks.keys()]
            await callback.message.answer('Выбери предмет',
                                          reply_markup=custom_keyboard(callback_back_button='start_menu',
                                                                       main_callback='start_homeworks',
                                                                       buttons=buttons).as_markup())

        else:
            buttons = [(x, f'subj={x}') for x in homeworks.homeworks.keys()]
            try:
                await callback.message.edit_text('Домашние задания ещё не добавлены',
                                                 reply_markup=custom_keyboard(callback_back_button='start_menu',
                                                                              main_callback='start_homeworks',
                                                                              buttons=buttons).as_markup())
            except TelegramBadRequest:
                await callback.message.edit_text('И тут не добавлены',
                                                 reply_markup=custom_keyboard(callback_back_button='start_menu',
                                                                              main_callback='start_homeworks',
                                                                              buttons=buttons).as_markup())

    else:
        if homeworks.homeworks:
            buttons = [(x, f'subj={x}') for x in homeworks.homeworks.keys()]
            await callback.message.edit_text('Выбери предмет',
                                             reply_markup=custom_keyboard(callback_back_button='start_menu',
                                                                          main_callback='start_homeworks',
                                                                          buttons=buttons).as_markup())
        else:
            try:
                await callback.message.edit_text('Домашние задания не добавлены',
                                                 reply_markup=standard_keyboard(user).as_markup())
            except TelegramBadRequest:
                await callback.message.edit_text('Домашние задания всё ещё не добавлены',
                                                 reply_markup=standard_keyboard(user).as_markup())


async def get_and_send_workshops(bot: Bot, user: User, callback: CallbackQuery):
    workshops: Workshops = await WorkshopsDB.select_workshops(user.groups[0][0])
    semester = '2 семестр' if 1 < datetime.now().month < 7 else '1 семестр'

    if 'num' in callback.data:
        subject = callback.data.split('_')[2].replace('subject=', '')
        num = callback.data.split('_')[3].replace('num=', '')

        workshops_list = workshops.workshops[semester][subject]

        try:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
        except TelegramBadRequest:
            pass

        for i, book in enumerate(workshops_list):
            if book['num'] == num:
                try:
                    room = f'\n\n📍 {workshop_rooms[subject][book['num']]}'
                except KeyError:
                    room = ''

                await callback.message.answer(book['name'].replace('_', ' ') + room)

                await bot.send_document(chat_id=callback.message.chat.id,
                                        document=book['tg_file_id'])

    if 'subject' in callback.data or len(workshops.workshops[semester].keys()) == 1:
        if len(workshops.workshops[semester].keys()) == 1:
            subject = list(workshops.workshops[semester].keys())[0]
        else:
            subject = callback.data.split('_')[2].replace('subject=', '')

        workshops_list = workshops.workshops[semester][subject]
        buttons = natsorted([(x['num'], f'subject={subject}_num={x['num']}') for x in workshops_list])

        if len(workshops.workshops[semester].keys()) > 1:
            callback_back_button = 'start_workshops'
        else:
            callback_back_button = 'start_menu'

        try:
            await callback.message.edit_text('Выбери номер практикума',
                                             reply_markup=custom_keyboard(main_callback='start_workshops',
                                                                          buttons=buttons,
                                                                          callback_back_button=callback_back_button,
                                                                          buttons_in_row=5).as_markup())
        except TelegramBadRequest:
            await callback.message.answer('Выбери номер практикума',
                                          reply_markup=custom_keyboard(main_callback='start_workshops',
                                                                       buttons=buttons,
                                                                       callback_back_button=callback_back_button,
                                                                       buttons_in_row=5).as_markup())

    else:
        buttons = list(workshops.workshops['1 семестр'].keys())
        buttons = [(x, f'subject={x}') for x in buttons]

        await callback.message.edit_text('Выбери предмет',
                                         reply_markup=custom_keyboard(main_callback='start_workshops',
                                                                      buttons=buttons,
                                                                      callback_back_button='start_menu',
                                                                      buttons_in_row=5).as_markup())


async def get_and_send_books(bot: Bot, user: User, callback: CallbackQuery):
    books: Books = await BooksDB.select_books(user.groups[0][0])
    semester = '2 семестр' if 1 < datetime.now().month < 7 else '1 семестр'

    if books.books:
        # Если предмет выбран, выводим все учебники по нему
        if 'subject' in callback.data:
            subject = callback.data.replace('start_books_subject=', '')

            media = []
            try:
                await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
            except TelegramBadRequest:
                pass

            for num, book in enumerate(books.books[semester][subject]):
                if books.books[semester][subject][num]['type'] == 'document':
                    media.append(InputMediaDocument(media=books.books[semester][subject][num]['tg_file_id']))

                else:
                    media.append(InputMediaPhoto(media=books.books[semester][subject][num]['tg_file_id']))

            await callback.message.answer(f'*{semester}, {subject}*',
                                          parse_mode='Markdown')

            await bot.send_media_group(chat_id=callback.message.chat.id,
                                       media=media)

        buttons = list(books.books['1 семестр'].keys())
        buttons = [(x, f'subject={x}') for x in buttons]

        try:
            await callback.message.edit_text('Выбери предмет',
                                             reply_markup=custom_keyboard(main_callback='start_books',
                                                                          buttons=buttons,
                                                                          callback_back_button='start_menu').as_markup())
        except TelegramBadRequest:
            await callback.message.answer('Выбери предмет',
                                          reply_markup=custom_keyboard(main_callback='start_books',
                                                                       buttons=buttons,
                                                                       callback_back_button='start_menu').as_markup())

    else:
        try:
            await callback.message.edit_text('Учебники ещё не добавлены',
                                             reply_markup=standard_keyboard(user).as_markup())
        except TelegramBadRequest:
            await callback.message.edit_text('Учебники всё ещё не добавлены',
                                             reply_markup=standard_keyboard(user).as_markup())


async def process_session_schedule(bot: Bot, user: User, callback: CallbackQuery):
    if 'group' in callback.data:
        group = callback.data.replace('start_session_group=', '')
    else:
        group = user.groups[0]

    table = PrettyTable(hrules=ALL)

    if user.settings.full_schedule:
        table.field_names = ['Дата', 'Предмет', 'Преп', 'Каб.']
        table._max_width = {"Дата": 5, "Предмет": 11, 'Преп': 5, "Каб.": 3}
    else:
        table._max_width = {"Дата": 5, "Предмет": 14, "Кабинет": 5}
        table.field_names = ['Дата', 'Предмет', 'Кабинет']

    exams = await SessionDB.select(group)

    if exams:
        for exam in exams:
            if user.settings.full_schedule:
                table.add_row([f'{exam.exam_datetime.strftime('%d.%m %H:%M')}',
                               exam.name, exam.teacher, exam.room])
            else:
                table.add_row([f'{exam.exam_datetime.strftime('%d.%m %H:%M')}',
                               exam.name, exam.room])

        remaining_exams = [exam for exam in exams if exam.exam_datetime > datetime.now()]
        count_remaining_exams = len(remaining_exams)

        if count_remaining_exams > 4:
            answer = f'Тебе осталось всего {count_remaining_exams} экзаменов\n\n'
        elif count_remaining_exams > 1:
            answer = f'Тебе осталось всего {count_remaining_exams} экзамена\n\n'
        else:
            answer = 'Тебе остался всего 1 экзамен\n\n'

        answer += f'```\n{table}```\n\nДо ближайшего экзамена осталось '
        distance_between_datetimes = remaining_exams[0].exam_datetime - datetime.now()

        hours, remainder = divmod(distance_between_datetimes.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if distance_between_datetimes.days > 0:
            if distance_between_datetimes.days > 4:
                answer += f'{distance_between_datetimes.days} дней '
            elif distance_between_datetimes.days > 1:
                answer += f'{distance_between_datetimes.days} дня '
            else:
                answer += f'{distance_between_datetimes.days} день '

        if hours > 0:
            if hours in [2, 3, 4, 22, 23]:
                answer += f'{hours} часа '
            elif hours in [1, 21]:
                answer += f'{hours} час '
            else:
                answer += f'{hours} часов '

        if minutes > 0:
            if minutes in [2, 3, 4, 22, 23, 24, 32, 33, 34, 42, 43, 44, 52, 53, 54]:
                answer += f'{minutes} минуты '
            elif minutes in [1, 21, 31, 41, 51]:
                answer += f'{minutes} минута '
            else:
                answer += f'{minutes} минут '

        if seconds > 0:
            if seconds in [2, 3, 4, 22, 23, 24, 32, 33, 34, 42, 43, 44, 52, 53, 54]:
                answer += f'{minutes} минут '
            elif seconds in [1, 21, 31, 41, 51]:
                answer += f'{seconds} секунда'
            else:
                answer += f'{seconds} секунд'

        answer += (
            '\n\n_P\\.s\\. В расписании могут быть ошибки\\. На всякий случай проверьте по файлу от учебной части_\n'
            '_P\\.p\\.s\\. Формат отображения \\(вывод преподавателей\\) можно изменить в настройках_')
        buttons = [(other_group, f'group={other_group}') for other_group in user.groups if other_group != group]
        await callback.message.edit_text(text=answer,
                                         reply_markup=custom_keyboard(callback_back_button='start_menu',
                                                                      main_callback='start_session',
                                                                      buttons=buttons,
                                                                      buttons_in_row=5).as_markup(),
                                         parse_mode='MarkdownV2')

    else:
        await callback.message.answer_animation(
            'CAACAgIAAxkBAAOzZtEDiMShfT_Mjh5sC4_3aGe6vhEAAicAA1m7_CWHZQZEF1WF-DUE')
        buttons = [(other_group, f'group={other_group}') for other_group in user.groups if other_group != group]
        await callback.message.answer(text='Неловко-то как!.. Кажется, я не смог найти твоё расписание. '
                                           'Уже сообщил, куда следует.. 😳',
                                      reply_markup=custom_keyboard(callback_back_button='start_menu',
                                                                   main_callback='start_session',
                                                                   buttons=buttons,
                                                                   buttons_in_row=5).as_markup())
