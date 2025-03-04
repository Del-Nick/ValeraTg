import asyncio
import json
import re
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from prettytable import PrettyTable, ALL, FRAME

from Files.Files import schedule, load_schedule
from Handlers.Keyboards import standard_keyboard
from Scripts.Arrays import GROUPS
from Scripts.Others import remove_inline_keyboard
from Server.Core import LessonScheduleDB, CustomLessonScheduleDB
from Server.Models import User, WeekType
from Handlers.Keyboards import schedule_keyboard, empty_keyboard

weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']


def reload_schedule():
    global schedule
    schedule = load_schedule()

    return True if schedule else False


def get_day_and_group(user: User, callback: CallbackQuery, group: str = None):
    day = datetime.today().weekday()

    if not group:
        if callback.data == 'start_schedule':
            group = user.groups[0]
        else:

            if 'week' in callback.data:
                day = datetime.today().weekday()
            else:
                day = int(re.search(r'day=\d', callback.data).group().replace('day=', ''))

            if 'group' in callback.data:
                group = re.search(r'group=\d{3}[a-я]{0,3}', callback.data).group().replace('group=', '')
            else:
                group = user.groups[0]

    return day, group


def get_weeks_data(user: User, data: str, day: int):
    week_number = datetime.today().isocalendar().week - 5
    date = datetime.now() - timedelta(days=datetime.now().weekday() - day)

    if day == 6:
        day = 0
        date += timedelta(days=1)
        week_number += 1

    else:
        if datetime.now().time() > user.settings.tomorrow_schedule_after:
            if data == 'start_schedule':
                if day == 5:
                    day = 0
                    date += timedelta(days=2)
                    week_number += 1

                else:
                    day += 1
                    date += timedelta(days=1)

            elif datetime.now().weekday() > 4:
                date += timedelta(days=7)
                week_number += 1

    return day, date, week_number


async def schedule_builder(bot: Bot, user: User, message: Message = None, callback: CallbackQuery = None,
                           group: str = None):
    day, group = get_day_and_group(user, callback, group)
    day, date, week_number = get_weeks_data(user, callback.data, day) if callback else get_weeks_data(user,
                                                                                                      message.text, day)

    lessons = await LessonScheduleDB.select(group_name=group, weekday=day,
                                            week_type=WeekType.ODD if week_number % 2 == 1 else WeekType.EVEN)
    custom_lessons = await CustomLessonScheduleDB.select(group_name=group, weekday=day,
                                                         week_type=WeekType.ODD if week_number % 2 == 1 else WeekType.EVEN)

    for i, lesson in enumerate(lessons):
        for custom_lesson in custom_lessons:
            if custom_lesson:
                if (custom_lesson.group_id == lesson.group_id and
                        custom_lesson.weekday == lesson.weekday and
                        custom_lesson.week_type == lesson.week_type and
                        custom_lesson.lesson_number == lesson.lesson_number):
                    lessons[i] = custom_lesson

    name_day = weekdays[day]
    answer = f'Расписание для группы {group}\n\n' if group != user.groups[0] else ''
    answer += (f'{name_day.upper()}, {date.strftime('%d.%m')}       '
               f'Неделя №{week_number}\n\n').replace('.', r'\.')

    time = ['09:0010:35', '10:5012:25', '13:3015:05', '15:2016:55', '17:0518:40',
            '18:5520:30']

    table = PrettyTable(hrules=ALL)
    if user.settings.full_schedule:
        table.field_names = ['Время', 'Предмет', 'Преп', 'Каб.']
        table._max_width = {"Время": 5, "Предмет": 8, 'Преп': 8, "Каб.": 3}
    else:
        table._max_width = {"Время": 5, "Предмет": 16, "Кабинет": 7}
        table.field_names = ['Время', 'Предмет', 'Кабинет']

    if lessons:
        if lessons[0].lesson_number > 0:
            for _ in range(lessons[0].lesson_number - 1):
                table.add_row([time[_], '', '', '']) if user.settings.full_schedule \
                    else table.add_row([time[_], '', ''])

        for lesson in lessons:
            if user.settings.full_schedule:
                table.add_row([time[lesson.lesson_number - 1], lesson.lesson, lesson.teacher, lesson.room])

            else:
                table.add_row([time[lesson.lesson_number - 1], lesson.lesson, lesson.room])

        answer += '```\n' + table.get_string() + '\n```'

        if len(lessons) == 1:
            answer += '\nУ тебя 1 пара'
        elif 0 < len(lessons) < 5:
            answer += f'\nУ тебя {len(lessons)} пары'
        else:
            answer += f'\nУ тебя {len(lessons)} пар'

        if callback:
            await callback.message.edit_text(text=answer,
                                             reply_markup=schedule_keyboard(user, day=day, group=group).as_markup(),
                                             parse_mode='MarkdownV2')
        else:
            await message.answer(text=answer,
                                 reply_markup=schedule_keyboard(user, day=day, group=group).as_markup(),
                                 parse_mode='MarkdownV2')

    else:
        answer += '```\n' + table.get_string() + '\n```'
        answer += f'\nУ тебя нет пар'

        if callback:
            await callback.message.edit_text(text=answer,
                                             reply_markup=schedule_keyboard(user, day=day, group=group).as_markup(),
                                             parse_mode='MarkdownV2')
        else:
            await message.answer(text=answer,
                                 reply_markup=schedule_keyboard(user, day=day, group=group).as_markup(),
                                 parse_mode='MarkdownV2')
