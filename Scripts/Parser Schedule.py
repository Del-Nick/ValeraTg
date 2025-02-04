import asyncio
import json
import re
import time
from pprint import pprint

import aiohttp
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from tqdm import tqdm
from selenium.webdriver import Chrome, ChromeOptions

chrome_options = Options()
chrome_options.add_argument('--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) '
                            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1')
chrome_options.add_argument('headless')
chrome_options.add_argument('window-size=1200x600')

driver = Chrome(options=chrome_options)


async def check_the_boundaries_for_URLs():
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) '
                      'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'}

    pages = {}

    for course in range(1, 7):
        pages[course] = {}
        pages_set = set()

        for part in range(1, 6):
            for num_page in range(1, 20):
                url = f'http://ras.phys.msu.ru/table/{course}/{part}/{num_page}.htm'

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        result = await response.text()

                if result in pages_set or 'НЕТ ДАННЫХ' in result:
                    if num_page != 1:
                        pages[course][part] = num_page

                    break

                else:
                    pages_set.add(result)

    pprint(pages)


def get_dict_with_pages() -> dict:
    '''
    Функция проверяет, на каких страницах есть расписание
    и возвращает список с последними номерами страниц
    :return:
    '''
    pages = {}
    for course in range(1, 7):
        pages[course] = {}
        last_part = 4 if course < 3 else 3
        for part in range(1, last_part):
            for num_page in range(1, 30):
                url = f'http://ras.phys.msu.ru/table/{course}/{part}/{num_page}.htm'
                headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B137 Safari/601.1'}
                request = requests.get(url, headers=headers)
                if 'НЕТ ДАННЫХ' in request.text:
                    pages[course][part] = num_page
                    break
    return pages


def get_table_from_web(url: str) -> object:
    """
    Подключается к сайту и возращает таблицу из тега
    :param url:
    :return:
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) '
                      'Version/14.0 Mobile/15E148 Safari/604.1'}

    driver.get(url)

    while True:
        elements = driver.find_elements(By.XPATH, "/html/body/table/tbody/tr/td[@class='tditem1']")
        if all([td_value.text == ' ' for td_value in elements]):
            time.sleep(1)
            driver.refresh()
            body = driver.find_element(By.XPATH, "/html/body/table/tbody/tr/td")

            if body.text == 'НЕТ ДАННЫХ':
                break

        else:
            driver.get(url)
            html = driver.find_element(By.XPATH, "/html").get_attribute('innerHTML')
            soup = BeautifulSoup(html, 'html5lib')
            break

    return soup.find('table', class_='hTable')


def change_masters_group_to_specialty(text: str):
    """
    В расписании, в шапке, указаны группы специалитета, а в таблице — магистратуры. Исправляем
    :param text:
    :return: Текст с исправленными группами
    """
    patterns = [r'1\d{2}М\w?', r'2\d{2}М\D?', r'1\d{2}м\D?', r'2\d{2}м\D?']
    matches = sum([re.findall(pattern, text) for pattern in patterns], [])

    for match in matches:
        new_group = '5' + match.lower()[1:] if match[0] == '1' else '6' + match.lower()[1:]
        new_group = new_group.replace('м', '').replace('М', '')
        text = text.replace(match, new_group)

    return text


def get_groups(data: list) -> list:
    """
    Возвращает список всех групп, которые упоминаются в расписании
    :param data: список данных, в которых могут быть группы
    :return: список групп
    """

    if type(data[0]) is list:
        return list(set(re.findall(r'\d{3}\w{0,2}', ' '.join([i[0] for i in data]))))

    else:
        return list(set(re.findall(r'\d{3}\w{0,2}', ' '.join(data))))


def get_num_lesson(time: str) -> int:
    """
    Просто возвращает номер текущей пары на основе времени в ячейке
    :param time: время из ячейки
    :return: номер пары
    """
    if time == '9:00':
        lesson = 1
    elif time == '10:50':
        lesson = 2
    elif time == '13:30':
        lesson = 3
    elif time == '15:20':
        lesson = 4
    elif time == '17:05':
        lesson = 5
    elif time == '18:55':
        lesson = 6
    else:
        lesson = None

    return lesson


def get_weekday(num_weekday: int) -> str:
    weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
    return weekdays[num_weekday]


def get_all_info_about_lesson(line: list, group: str, groups: list) -> dict:
    """
    Разбираем список из ячейки расписания на словарь типа
    {'lesson': lesson, 'room': room, 'teacher': teacher}
    :param line: список данных из ячейки
    :param group: группа, для которой заполняется расписание
    :param groups: список групп, для которых есть расписание на странице
    :return: словарь типа {'lesson': lesson, 'room': room, 'teacher': teacher}
    """

    group_lower = group.lower()

    # Индекс, с которого начинается расписание для нужной группы
    start_index = 0

    # Проверяем, расписание в ячейке для одной группы или для нескольких
    if re.search(r'\d{1} поток без \d{3}\w{0,2}', line[0]):
        if group in line[0]:
            return {'even': {'lesson': '',
                             'room': '',
                             'teacher': ''},
                    'odd': {'lesson': '',
                            'room': '',
                            'teacher': ''}}
        else:
            line[0] = line[0].split(' - ')[1]

    elif re.search(r'\d{3}\w{0,2}', line[0]):
        if group in ' '.join(line):
            # Ищем элемент, с которого начинается расписание для нужной группы
            for start_index, elem in enumerate(line):
                if group_lower in elem.lower():
                    break

        else:
            return {'even': {'lesson': '',
                             'room': '',
                             'teacher': ''},
                    'odd': {'lesson': '',
                            'room': '',
                            'teacher': ''}}

    # Бывают строки типа '303 - С/К по выбору, 340 - ФТД ', поэтому делаем проверку на такое
    if len(re.findall(r'\d{3}\w{0,2} - ', line[start_index])) > 1:
        lesson = line[start_index].split(', ')
        for i in lesson:
            if group in i:
                lesson = i.replace(' - ', '')
                break
    else:
        lesson = line[start_index].replace(' - ', '')

    # Если для разных групп разные условия, разделяем на список и выбираем только нужную группу
    if ('по выбору' in lesson) and ('обяз' in lesson):
        for i in lesson.split(', '):
            if group in i:
                lesson = i
                break

    lesson.replace(group, '')

    # Удаляем все повтроения группу типа '406+415+416...'
    if re.search(r'\d{3}', lesson):
        for i in groups:
            lesson = lesson.replace(i, '')
        lesson = lesson.replace('+', '').replace(', ', '')

    # Иногда почему-то время пишут в расписании, поэтому его тоже удаляем
    if re.search(r'\d{2}.\d{2}', lesson):
        for i in re.findall(r'\d{2}.\d{2}', lesson):
            lesson = lesson.replace(i, '')

    # Для делений на подгруппы несколько кабинетов и преподавателей
    if line.count('Иностранный язык ') > 1:
        room = []
        teacher = []
        for i in range(line.count('Иностранный язык ')):
            room.append(line[3 * i + 1])
            teacher.append(line[3 * i + 2])
        room = ' / '.join(room)
        teacher = ' / '.join(teacher)

        teacher = teacher.replace('/ ', '/')
    else:
        room = line[start_index + 1] if start_index + 1 < len(line) else ''
        teacher = line[start_index + 2] if start_index + 2 < len(line) else ''

    def remove_extra_spaces(text: str) -> str:
        if len(text) > 0:
            while text[0] in (' ', ','):
                text = text[1:]
            if text[-1] == ' ':
                text = text[:-1]
        return text

    lesson = remove_extra_spaces(lesson).replace('- ', '')
    teacher = remove_extra_spaces(teacher)

    if line[-1] == 'even':
        return {'even': {'lesson': lesson,
                         'room': room,
                         'teacher': teacher}}
    elif line[-1] == 'odd':
        return {'odd': {'lesson': lesson,
                        'room': room,
                        'teacher': teacher}}
    else:
        return {'even': {'lesson': lesson,
                         'room': room,
                         'teacher': teacher},
                'odd': {'lesson': lesson,
                        'room': room,
                        'teacher': teacher}}


def do_initial_data_processing(url: str) -> tuple:
    """
    Разделяет всю информацию по тегу <td>, добавляет метки чётности недели,
    ищет все группы на странице и те из них, для которых расписание есть на этой странице
    :param url: адрес расписания
    :return: список данных для разбора, группы с расписанием и все группы
    """
    table = get_table_from_web(url)

    table_to_list = table.find_all('td')
    lines = []

    for i, line in enumerate(table_to_list):
        new_line = change_masters_group_to_specialty(line.get_text(separator='~').replace('\xa0', ' '))

        if 'tdsmall1' in str(line):
            # Класс 'tdtime' отвечает за хранение времени пар, расположен перед ячейкой с расписанием
            if 'tdtime' in str(table_to_list[i - 1]):
                new_line = new_line + '~even'
            elif 'tdtime' in str(table_to_list[i - 2]):
                new_line = new_line + '~odd'

        if 'tbody' in str(line):
            new_line = ''
        elif 'tdsmall0' in str(line) and (
                'tdsmall1' in str(table_to_list[i - 1]) or 'tdsmall1' in str(table_to_list[i - 2])):
            # Внутри этого if проверяем, не додумался ли создатель расписания запихать разные условия для мигающих пар
            if 'tdtime' in str(table_to_list[i - 1]) or 'tdtime' in str(table_to_list[i - 2]):
                new_line = new_line + '~even'
            elif 'tdtime' in str(table_to_list[i - 3]) or 'tdtime' in str(table_to_list[i - 4]):
                new_line = new_line + '~odd'

        lines.append(new_line.split('~'))

    lines = lines[3:-1]
    groups = get_groups(lines[0])
    all_groups = get_groups(lines)

    # Ищем, с какого индекса начинается расписание
    for start, line in enumerate(lines):
        if line[0] == '9:00':
            break
    lines = lines[start:]

    return lines, groups, all_groups


def fill_gaps(schedule: dict) -> dict:
    weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']

    # Сюда записываем координаты пустых пар в формате [группа, день недели, пара]
    garbage = []

    with tqdm(total=len(schedule.keys())) as pbar:
        pbar.set_description(f"Заполняю дыры")
        for group in schedule.keys():
            for weekday in weekdays:
                if weekday not in schedule[group].keys():
                    schedule[group][weekday] = {}
                else:
                    for lesson in schedule[group][weekday].keys():
                        temp = schedule[group][weekday][lesson]
                        if 'even' not in temp.keys():
                            schedule[group][weekday][lesson]['even'] = {'lesson': '',
                                                                        'room': '',
                                                                        'teacher': ''}
                        if 'odd' not in temp.keys():
                            schedule[group][weekday][lesson]['odd'] = {'lesson': '',
                                                                       'room': '',
                                                                       'teacher': ''}

                        if temp['even']['lesson'] == '' and temp['odd']['lesson'] == '':
                            garbage.append([group, weekday, lesson])

            pbar.update()

    for i in garbage:
        del schedule[i[0]][i[1]][i[2]]

    return schedule


def save_schedule_to_json(schedule: dict, filename: str):
    with open(filename, 'w+', encoding='utf-8') as f:
        json.dump(schedule, f, ensure_ascii=False)


def main():
    print('Структура расписания:\n\n'
          '{group: \n'
          '|------{weekday: \n'
          '|-------------{num_lesson: \n'
          '|-----------------------{even: \n'
          '|----------------------------{lesson: value,\n'
          '|-----------------------------room: value,\n'
          '|-----------------------------teacher: value}\n'
          '|-----------------------{odd: \n'
          '|----------------------------{lesson: value,\n'
          '|-----------------------------room: value,\n'
          '|-----------------------------teacher: value}}}}}\n\n')
    schedule = {}
    # Можно проверить, не изменилось ли количество страниц
    # pages = get_dict_with_pages()
    pages = {1: {1: 9, 2: 9},
             2: {1: 9, 2: 9},
             3: {1: 11, 2: 9},
             4: {1: 11, 2: 11},
             5: {1: 13, 2: 11},
             6: {1: 12, 2: 11}}

    # Общее количество страниц нужно только для progress bar
    total_pages = 0
    for course in pages.values():
        for value in course.values():
            total_pages += value - 1

    with tqdm(total=total_pages) as pbar:
        for course in list(pages.keys()):
            for part in pages[course].keys():
                for page in range(1, pages[course][part]):
                    url = f'http://ras.phys.msu.ru/table/{course}/{part}/{page}.htm'

                    lines, groups, all_groups = do_initial_data_processing(url)

                    for group in sorted(groups, key=len, reverse=True):
                        weekday = 'Понедельник'
                        schedule[group.lower()] = {weekday: {}}
                        num_weekday = -1

                        # А теперь уже проверяем все строки на наличие расписания для нужной группы
                        for index, line in enumerate(lines):
                            # Проверяем, есть ли время в ячейке
                            if re.search(r'\d{1,2}:\d{2}', line[0]):
                                lesson = get_num_lesson(line[0])
                                if lesson == 1:
                                    num_weekday += 1
                                    weekday = get_weekday(num_weekday)
                                    schedule[group.lower()][weekday] = {}

                            elif line[0] == '' or line[0] == ' ':
                                pass

                            else:
                                if lesson not in schedule[group.lower()][weekday].keys():
                                    schedule[group.lower()][weekday][lesson] = get_all_info_about_lesson(line, group,
                                                                                                       all_groups)

                                else:
                                    temp = get_all_info_about_lesson(line, group, all_groups)
                                    if 'even' in temp.keys():
                                        if temp['even']['lesson'] != '':
                                            schedule[group.lower()][weekday][lesson]['even'] = temp['even']
                                    if 'odd' in temp.keys():
                                        if temp['odd']['lesson'] != '':
                                            schedule[group.lower()][weekday][lesson]['odd'] = temp['odd']

                    pbar.update(1)
                    pbar.set_description(desc=url)

    schedule = fill_gaps(schedule)

    pprint(schedule)

    # with open('../Files/Schedule.json', mode='r', encoding='utf-8') as f:
    #     old_schedule = json.load(f)

    # pprint(schedule['204'])
    # pprint(test(old_schedule, schedule))
    save_schedule_to_json(schedule, filename='../Files/Schedule.json')
    save_schedule_to_json(schedule, filename='../../Valera/Files/Schedule.json')


def get_difference_between_new_and_old_schedule(old: dict, new: dict):
    for group in list(old.keys())[:4]:
        for day in old[group].keys():
            for lesson in old[group][day].keys():
                for parity in old[group][day][lesson].keys():
                    old_set = {group, day, lesson, parity, tuple(old[group][day][lesson][parity].items())}
                    try:
                        new_set = {group, day, lesson, parity, tuple(new[group][day][lesson][parity].items())}
                        if old_set != new_set:
                            print(f'{group}     {old_set ^ new_set}')

                    except KeyError:
                        print(group, day, lesson)
                        pprint(old[group][day])
                        pprint(new[group][day])
                        print()


def test(dict1, dict2):
    differences = {}

    for key in set(dict1.keys()).union(dict2.keys()):
        if key not in dict1:
            differences[key] = {"status": "missing_in_first", "value": dict2[key]}
        elif key not in dict2:
            differences[key] = {"status": "missing_in_second", "value": dict1[key]}
        else:
            if isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
                nested_diff = test(dict1[key], dict2[key])
                if nested_diff:
                    differences[key] = nested_diff
            elif dict1[key] != dict2[key]:
                differences[key] = {"first": dict1[key], "second": dict2[key]}

    return differences


if __name__ == '__main__':
    main()