import asyncio
from difflib import get_close_matches
from io import BytesIO
from pprint import pprint
from queue import Queue

import aiogram
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery

from Handlers.Keyboards import custom_keyboard
from Scripts.FloorCabinetSearchEngine import reload_floor_schemas
from Scripts.RequestsToVK import get_vk_attachment
from Scripts.ScheduleBuilder import reload_schedule
from Server.Core import DB, WorkshopsDB, BooksDB
from Server.Models import User

file_senders: set[tuple] = set()
queue_workshops: Queue[dict] = Queue()
queue_books: Queue[dict] = Queue()


async def admin_handler(bot: Bot, admin: User, message: Message = None, callback: CallbackQuery = None):
    buttons = [('Редактировать старост', 'headmen'),
               ('Редактировать практикумы', 'workshop'),
               ('Редактировать учебники', 'book'),
               ('Обновить окружение', 'update')]

    if callback:
        if callback.data == 'admin_start':
            await callback.message.edit_text('Выбери раздел',
                                             reply_markup=custom_keyboard(main_callback='admin',
                                                                          buttons=buttons,
                                                                          callback_back_button='start_menu').as_markup())
            admin.action = 'admin_start'

        elif callback.data == 'admin_headmen':
            admin.action = 'admin_headmen'
            await edit_headmen(callback=callback, admin=admin)

        elif callback.data == 'admin_book':
            admin.action = 'admin_book'
            await edit_books(bot=bot, callback=callback, admin=admin)

        elif callback.data == 'admin_workshop':
            admin.action = 'admin_workshop'
            await edit_workshops(bot=bot, callback=callback, admin=admin)

        elif callback.data == 'admin_update':
            if not reload_schedule():
                desc = 'Не удалось найти расписание'
            else:
                desc = 'Расписание успешно обновлено'

            if not reload_floor_schemas():
                desc += '\nНе удалось найти схемы этажей'
            else:
                desc += '\nСхемы этажей успешно обновлены'

            await callback.message.edit_text(desc,
                                             reply_markup=custom_keyboard(main_callback='admin',
                                                                          buttons=buttons,
                                                                          callback_back_button='start_menu').as_markup())

    else:
        if admin.action == 'admin_start':
            try:
                await bot.edit_message_reply_markup(chat_id=message.chat.id,
                                                    message_id=message.message_id - 1,
                                                    reply_markup=None)
            except TelegramBadRequest:
                pass

            await message.answer('Выбери раздел',
                                 reply_markup=custom_keyboard(main_callback='admin',
                                                              buttons=buttons,
                                                              callback_back_button='start_menu').as_markup())
        elif admin.action == 'admin_workshop':
            await edit_workshops(bot=bot, message=message, admin=admin)

        elif admin.action == 'admin_book':
            await edit_books(bot=bot, message=message, admin=admin)

        elif admin.action == 'admin_headmen':
            await edit_headmen(message=message, admin=admin)


async def edit_headmen(admin: User, message: Message = None, callback: CallbackQuery = None):
    if callback:
        if callback.data == 'admin_headmen':
            await callback.message.edit_text(text='Доступны команды:\n\n'
                                                  '     · *добавить*\n'
                                                  '     · *удалить*\n\n'
                                                  'Структура запроса:\n\n'
                                                  '     · _добавить \\-ник в тг\n'
                                                  '     · удалить \\-ник в тг_\n\n'
                                                  'Пример запроса:\n\n'
                                                  '     · добавить \\-DelNick99',
                                             reply_markup=custom_keyboard(
                                                 callback_back_button='admin_start').as_markup(),
                                             parse_mode='MarkdownV2')

    else:
        try:
            cmd, nickname = message.text.replace('@', '').split(' -')
            user = await DB.select_user(TgName=nickname) if nickname != admin.TgName else admin

            if user:
                match cmd:
                    case 'добавить':
                        user.settings.headman = True
                        await message.answer(
                            f'Пользователю @{nickname} предоставлены права старосты группы {user.groups[0]}',
                            reply_markup=custom_keyboard(callback_back_button='admin_start').as_markup())

                    case 'удалить':
                        user.settings.headman = False
                        await message.answer(
                            f'Пользователь @{nickname} больше не староста группы {user.groups[0]}',
                            reply_markup=custom_keyboard(callback_back_button='admin_start').as_markup())

                    case _:
                        await message.answer(
                            f'Проверь правильность ввода команды. Поддерживаются только *добавить* и *удалить*',
                            reply_markup=custom_keyboard(callback_back_button='admin_start').as_markup(),
                            parse_mode='Markdown')

                await DB.update_user(user)

            else:
                names = await DB.get_all_tg_names()
                variants = [f'@{x}' for x in get_close_matches(nickname, names, 5)]

                if variants:
                    await message.answer(f'Не смог найти пользователя @{nickname} в своей базе данных. '
                                         f'Я постарался найти похожие варианты:\n\n'
                                         f'     {'\n     · '.join(variants)}\n\n'
                                         f'Если нужного нет, убедись, что @{nickname} писал мне раньше в телеграме',
                                         reply_markup=custom_keyboard(callback_back_button='admin_start').as_markup())
                else:
                    await message.answer(f'Не смог найти пользователя @{nickname} в своей базе данных. '
                                         f'Он точно писал мне раньше в телеграме?',
                                         reply_markup=custom_keyboard(callback_back_button='admin_start').as_markup())

        except ValueError:
            await message.answer('Не смог распознать команду. Оформляй по образцу, который я тебе присылал. '
                                 'Не забывай про дефис перед параметрами!',
                                 reply_markup=custom_keyboard(callback_back_button='admin_start').as_markup())


async def edit_workshops(bot: Bot, admin: User, message: Message = None, callback: CallbackQuery = None):
    if callback:
        await callback.message.edit_text(text='Доступны команды:\n\n'
                                              '     · *добавить*\n'
                                              '     · *удалить*\n\n'
                                              'Структура запроса:\n\n'
                                              '     · _добавить \\-курс \\-семестр \\-предмет\n'
                                              '     · удалить \\-курс \\-семестр \\-предмет \\-название_\n\n'
                                              'Для каждого курса доступны 2 семетра: 1 и 2\\. То есть 5 семестр '
                                              'преобразуется в 3 курс и 1 семестр\\. Дефис перед параметром '
                                              'обязателен\\! Для добавления необходимо прикрепить один файл\\. '
                                              'Регистр не важен\\. Пример запроса:\n\n'
                                              '     · добавить \\-3 \\-1 \\-Атомная физика',
                                         reply_markup=custom_keyboard(
                                             callback_back_button='admin_start').as_markup(),
                                         parse_mode='MarkdownV2')
    else:
        try:
            if message.text:
                data = message.text.split(' -')
                print(f'{data=}')
                if data[0] == 'добавить':
                    cmd, course, sem, subject = data
                    file_senders.add((message.from_user.id, cmd, course, sem, subject))

                    if cmd == 'добавить':
                        await remove_user_from_file_senders(bot=bot,
                                                            message=message,
                                                            data=(message.from_user.id, cmd, course, sem, subject),
                                                            )
                else:
                    cmd, course, sem, subject, filename = data
                    file_senders.add((message.from_user.id, cmd, course, sem, subject, filename))

                    if cmd == 'добавить':
                        await remove_user_from_file_senders(bot=bot,
                                                            message=message,
                                                            data=(
                                                                message.from_user.id, cmd, course, sem, subject,
                                                                filename))

                print(f'{cmd=}')

            elif message.caption:
                data = message.caption.split(' -')
                if data[0] == 'добавить':
                    cmd, course, sem, subject = data
                else:
                    cmd, course, sem, subject, filename = data

            else:
                # Сообщение приходит с первым файлом пользователя, однако он может загрузиться не первым.
                # Если инструкции ещё не поступали, ждём
                await asyncio.sleep(1)

                if message.from_user.id in [x[0] for x in file_senders]:
                    data = next(x for x in file_senders if x[0] == message.from_user.id)

                    if data[1] == 'добавить':
                        _, cmd, course, sem, subject = data
                    else:
                        _, cmd, course, sem, subject, filename = data

                else:
                    cmd = None
                    await message.answer('Не смог распознать команду. Оформляй по образцу, который я тебе присылал. '
                                         'Не забывай про дефис перед параметрами!',
                                         reply_markup=custom_keyboard(callback_back_button='admin_start').as_markup())

            if cmd:
                print(cmd)
                match cmd:
                    case 'добавить':
                        if message.document:
                            file = message.document
                            media_type = 'document' if message.document else 'photo'

                            data = BytesIO()

                            try:
                                await bot.download(file.file_id, data)
                                vk_file_id = await get_vk_attachment(data=data, filename=file.file_name)

                            except aiogram.exceptions.TelegramBadRequest:
                                vk_file_id = None

                            if '_' in file.file_name[:5]:
                                num = file.file_name.split('_')
                                num = '.'.join(num[0:2]) if num[1].isdigit() else num[0]

                            else:
                                num = file.file_name.split('.')
                                num = '.'.join(num[0:2]) if num[1].isdigit() else num[0]

                            workshop = {'1 семестр': {}, '2 семестр': {}}
                            workshop[f'{sem} семестр'] = {subject: [{'num': num,
                                                                     'name': file.file_name,
                                                                     'type': media_type,
                                                                     'tg_file_id': file.file_id,
                                                                     'vk_file_id': vk_file_id}]}

                            queue_workshops.put(workshop)

                            answer = f'Запомнил методичку для {course} курса, {sem} семестра по предмету {subject}'
                            if not vk_file_id:
                                answer += (
                                    '\n\nТелеграм не позволяет боту загружать файлы больше 20 Мб\\. Этот учебник '
                                    'нужно будет '
                                    'загрузить по такой же схеме сообщением Вк группе Студсовета с таким названием\\:\n'
                                    f'*{file.file_name}*')
                            await answer_to_file(bot=bot,
                                                 message=message,
                                                 user=admin,
                                                 data=(message.from_user.id, cmd, course, sem, subject),
                                                 text=answer)

                    case 'удалить':
                        try:
                            workshops = await WorkshopsDB.select_workshops(course=course)

                            index = None
                            for i, workshop in enumerate(workshops.workshops[f'{sem} семестр'][subject]):
                                if workshop['name'] == filename:
                                    index = i
                                    break

                            if index:
                                deleted = workshops.workshops[f'{sem} семестр'][subject].pop(i)

                                buttons = [('Редактировать старост', 'headmen'),
                                           ('Редактировать практикумы', 'workshop'),
                                           ('Редактировать учебники', 'book'),
                                           ('Обновить окружение', 'update')]

                                await WorkshopsDB.update_workshops(workshops)

                                await bot.send_document(chat_id=message.chat.id,
                                                        document=deleted['tg_file_id'],
                                                        caption=deleted['name'])
                                await message.answer(f'Файл {deleted['name']} успешно удалён',
                                                     reply_markup=custom_keyboard(main_callback='admin',
                                                                                  buttons=buttons,
                                                                                  callback_back_button='start_menu').as_markup())

                            else:
                                await message.answer(
                                    'Не смог найти такой файл. Ты точно всё указал правильно?',
                                    reply_markup=custom_keyboard(callback_back_button='admin_start').as_markup())

                        except KeyError:
                            await message.answer('Не смог найти такой файл. Ты точно всё указал правильно?')

        except ValueError:
            await message.answer('Не смог распознать команду. Оформляй по образцу, который я тебе присылал',
                                 reply_markup=custom_keyboard(callback_back_button='admin_start').as_markup())


async def edit_books(bot: Bot, admin: User, message: Message = None, callback: CallbackQuery = None):
    if callback:
        await callback.message.edit_text(text='Доступны команды:\n\n'
                                              '     · *добавить*\n'
                                              '     · *удалить*\n\n'
                                              'Структура запроса:\n\n'
                                              '     · _добавить \\-курс \\-семестр \\-предмет\n'
                                              '     · удалить \\-курс \\-семестр \\-предмет \\-название_\n\n'
                                              'Для каждого курса доступны 2 семетра: 1 и 2\\. То есть 5 семестр '
                                              'преобразуется в 3 курс и 1 семестр\\. Дефис перед параметром '
                                              'обязателен\\! Для добавления необходимо прикрепить один файл\\. '
                                              'Регистр не важен\\. Пример запроса:\n\n'
                                              '     · добавить \\-3 \\-1 \\-Атомная физика',
                                         reply_markup=custom_keyboard(
                                             callback_back_button='admin_start').as_markup(),
                                         parse_mode='MarkdownV2')
    else:
        try:
            if message.text:
                data = message.text.split(' -')
                if data[0] == 'добавить':
                    cmd, course, sem, subject = data
                    file_senders.add((message.from_user.id, cmd, course, sem, subject))
                    await remove_user_from_file_senders(bot=bot,
                                                        message=message,
                                                        data=(message.from_user.id, cmd, course, sem, subject),
                                                        db_type='books')
                else:
                    cmd, course, sem, subject, filename = data
                    file_senders.add((message.from_user.id, cmd, course, sem, subject, filename))
                    await remove_user_from_file_senders(bot=bot,
                                                        message=message,
                                                        data=(
                                                            message.from_user.id, cmd, course, sem, subject, filename),
                                                        db_type='books')

            elif message.caption:
                data = message.caption.split(' -')
                if data[0] == 'добавить':
                    cmd, course, sem, subject = data
                else:
                    cmd, course, sem, subject, filename = data

            else:
                # Сообщение приходит с первым файлом пользователя, однако он может загрузиться не первым.
                # Если инструкции ещё не поступали, ждём
                await asyncio.sleep(1)

                if message.from_user.id in [x[0] for x in file_senders]:
                    data = next(x for x in file_senders if x[0] == message.from_user.id)

                    if data[1] == 'добавить':
                        _, cmd, course, sem, subject = data
                    else:
                        _, cmd, course, sem, subject, filename = data

                else:
                    cmd = None
                    await message.answer('Не смог распознать команду. Оформляй по образцу, который я тебе присылал. '
                                         'Не забывай про дефис перед параметрами!',
                                         reply_markup=custom_keyboard(callback_back_button='admin_start').as_markup())

            if cmd:
                match cmd:
                    case 'добавить':
                        if message.document:
                            file = message.document
                            media_type = 'document' if message.document else 'photo'

                            data = BytesIO()

                            try:
                                await bot.download(file.file_id, data)
                                vk_file_id = await get_vk_attachment(data=data, filename=file.file_name)

                            except aiogram.exceptions.TelegramBadRequest:
                                vk_file_id = None

                            if '_' in file.file_name[:5]:
                                num = file.file_name.split('_')
                                num = '.'.join(num[0:2]) if num[1].isdigit() else num[0]

                            else:
                                num = file.file_name.split('.')
                                num = '.'.join(num[0:2]) if num[1].isdigit() else num[0]

                            book = {'1 семестр': {}, '2 семестр': {}}
                            book[f'{sem} семестр'] = {subject: [{'num': num,
                                                                 'name': file.file_name,
                                                                 'type': media_type,
                                                                 'tg_file_id': file.file_id,
                                                                 'vk_file_id': vk_file_id}]}

                            queue_books.put(book)

                            answer = f'Запомнил методичку для {course} курса, {sem} семестра по предмету {subject}'
                            if not vk_file_id:
                                answer += (
                                    '\n\nТелеграм не позволяет боту загружать файлы больше 20 Мб\\. Этот учебник '
                                    'нужно будет'
                                    'загрузить по такой же схеме сообщением Вк группе Студсовета с таким названием\\:\n'
                                    f'*{file.file_name}*')
                            await answer_to_file(bot=bot,
                                                 message=message,
                                                 user=admin,
                                                 data=(message.from_user.id, cmd, course, sem, subject),
                                                 text=answer,
                                                 db_type='books')
        except ValueError:
            await message.answer('Не смог распознать команду. Оформляй по образцу, который я тебе присылал',
                                 reply_markup=custom_keyboard(callback_back_button='admin_start').as_markup())


async def remove_user_from_file_senders(bot: Bot, message: Message, data: tuple, db_type: str = 'workshops'):
    for t in range(20, -1, -1):
        try:
            await bot.edit_message_text(f'До начала обработки осталось {t} секунд',
                                        chat_id=message.chat.id,
                                        message_id=message.message_id - 1)
        except TelegramBadRequest:
            pass

        await asyncio.sleep(1)

    await update_workshops(message, data, db_type)
    file_senders.remove(data)


async def update_workshops(message: Message, data: tuple, db_type: str):
    if db_type == 'books':
        books = await BooksDB.select_books(course=data[2])
        pprint(books.books)

        if not books.books:
            books.books = {'1 семестр': {}, '2 семестр': {}}

        for book in list(queue_books.queue):
            for semester in ('1 семестр', '2 семестр'):
                for subject in book[semester].keys():
                    if semester in books.books.keys():
                        if subject in books.books[semester].keys():
                            books.books[semester][subject] += book[semester][subject]

                        else:
                            books.books[semester][subject] = book[semester][subject]

                    else:
                        books.books[semester] = book[semester]

            queue_books.get(book)

        await BooksDB.update_books(books)
        await message.answer('Сохранил учебники')

    else:
        workshops = await WorkshopsDB.select_workshops(course=data[2])

        if not workshops.workshops:
            workshops.workshops = {'1 семестр': {}, '2 семестр': {}}

        for workshop in list(queue_workshops.queue):
            for semester in ('1 семестр', '2 семестр'):
                for subject in workshop[semester].keys():
                    if semester in workshops.workshops.keys():
                        if subject in workshops.workshops[semester].keys():
                            workshops.workshops[semester][subject] += workshop[semester][subject]

                        else:
                            workshops.workshops[semester][subject] = workshop[semester][subject]

                    else:
                        workshops.workshops[semester] = workshop[semester]

            queue_workshops.get(workshop)

        await WorkshopsDB.update_workshops(workshops)
        await message.answer('Сохранил методички')


async def answer_to_file(bot: Bot, message: Message, user: User, data: tuple, text: str, db_type: str = 'workshops'):
    if data in file_senders:
        return

    file_senders.add(data)
    await remove_user_from_file_senders(bot=bot, message=message, data=data, db_type=db_type)
    await message.answer(text,
                         reply_markup=custom_keyboard(callback_back_button='admin_start').as_markup(),
                         parse_mode='MarkdownV2')
