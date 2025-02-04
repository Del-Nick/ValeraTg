import asyncio
from datetime import datetime
from pprint import pprint

import camelot
import pandas as pd
from tqdm import tqdm
import re

from Server.Core import SessionDB
from Server.Models import Exam

pdf_path = '../Расписание_спецы_зима_2024_группы.pdf'

# Извлечение таблиц с каждой страницы
tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')  # 'stream' подходит для таблиц без четких границ

# Объединение всех таблиц в один DataFrame
df_list = [table.df for table in tables]
full_df = pd.concat(df_list, ignore_index=True)

group = None


def process_specialitet() -> dict[list[Exam]]:
    session_schedule: dict[list[Exam]] = {}
    group = None

    for i, row in full_df[10:-1].iterrows():
        print(i, row)
        if re.search(r'\d{3}\s{0,1}[абAБ]{0,1}', row[4]):
            group = row[4].split('\n')[0].replace(' ', '').lower()
            session_schedule[group] = []

        else:
            if group:
                if row[0]:
                    if row[6][0].isupper():
                        teacher, shift = row[6], 0
                    else:
                        teacher, shift = row[7], 1

                    room = row[7 + shift] if row[8 + shift] == 'физфак' else f'{row[7 + shift]}, {row[8 + shift]}'
                    session_schedule[group].append(Exam(group=group,
                                                        name=row[4].replace('пртложения', 'приложения'),
                                                        teacher=teacher,
                                                        exam_datetime=datetime.strptime(f'{row[0]} {row[2]}',
                                                                                        '%d.%m.%Y %H:%M'),
                                                        room=room))
                else:
                    try:
                        session_schedule[group][-1].name += f' {row[4]}'
                    except:
                        pass

    return session_schedule


def process_magistracy() -> list[Exam]:
    session_schedule: list[Exam] = []

    for i, row in full_df[2:].iterrows():
        print(i, row)
        if re.search(r'\d{3}м[а,б,к]{0,1}', row[4]):
            group = row[4]
            if 'м' in group:
                group = f'6{group[1:].replace('м', '')}'
                print(f'{group = }')

            if group:
                if row[0]:
                    if row[8][0].isupper():
                        teacher, shift = row[8], 0
                    else:
                        teacher, shift = row[9], 1

                    room = row[9 + shift] if row[10 + shift] == 'физфак' else f'{row[9 + shift]}, {row[10 + shift]}'
                    session_schedule.append(Exam(group=group,
                                                 name=row[6].replace('пртложения', 'приложения'),
                                                 teacher=teacher,
                                                 exam_datetime=datetime.strptime(f'{row[0]} {row[2]}',
                                                                                 '%d.%m.%Y %H:%M'),
                                                 room=room))
        else:
            session_schedule[-1].name += f' {row[6]}'

    session_schedule[-1].name = 'Физические методы медицинской диагностики (ДМП по выбору)'
    session_schedule.append(Exam(group='620',
                                 name='Высокотемпературная сверхпроводимость (ДМП по выбору)',
                                 teacher='Кузьмичев С.А.',
                                 exam_datetime=datetime.strptime('24.01.2025 15:00',
                                                                 '%d.%m.%Y %H:%M'),
                                 room='2-03, кр. корп.'))
    return session_schedule


# session_schedule = process_specialitet()
# pprint(session_schedule)

session_schedule = [Exam(group='301',
                         name='Теоретическая механика',
                         teacher='Казаков К.А.',
                         exam_datetime=datetime.strptime('08.01.2025 10:00',
                                                         '%d.%m.%Y %H:%M'),
                         room='5-36'),
                    Exam(group='301',
                         name='Методы математической физики',
                         teacher='Токмачев М.Г.',
                         exam_datetime=datetime.strptime('13.01.2025 13:00',
                                                         '%d.%m.%Y %H:%M'),
                         room='5-44'),
                    Exam(group='301',
                         name='Атомная физика',
                         teacher='Воронина Е.Н.',
                         exam_datetime=datetime.strptime('19.01.2025 10:00',
                                                         '%d.%m.%Y %H:%M'),
                         room='5-24'),
                    Exam(group='301',
                         name='Радиофизика',
                         teacher='Косых Т.Б.',
                         exam_datetime=datetime.strptime('24.01.2025 10:00',
                                                         '%d.%m.%Y %H:%M'),
                         room='5-49')]


async def to_db():
    for exam in tqdm(session_schedule):
        await SessionDB.insert(exam)

asyncio.run(to_db())
