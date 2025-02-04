import json
from PIL import Image


def load_schedule():
    # подгружаем файл с расписанием
    try:
        with open(f'Files/Schedule.json', encoding='utf-8') as f:
            return json.load(f)

    except FileNotFoundError:
        return {}


def load_floor_schemas() -> tuple:
    global zero_floor_alpha, first_floor_alpha, second_floor_alpha, \
        third_floor_alpha, fourth_floor_alpha, fifth_floor_alpha

    try:
        # Схемы этажей
        zero_floor_alpha = Image.open(r'Files/Rooms/0 floor alpha.png').convert('RGBA')
        first_floor_alpha = Image.open(r'Files/Rooms/1 floor alpha.png').convert('RGBA')
        second_floor_alpha = Image.open(r'Files/Rooms/2 floor alpha.png').convert('RGBA')
        third_floor_alpha = Image.open(r'Files/Rooms/3 floor alpha.png').convert('RGBA')
        fourth_floor_alpha = Image.open(r'Files/Rooms/4 floor alpha.png').convert('RGBA')
        fifth_floor_alpha = Image.open(r'Files/Rooms/5 floor alpha.png').convert('RGBA')
        return zero_floor_alpha, first_floor_alpha, second_floor_alpha, \
            third_floor_alpha, fourth_floor_alpha, fifth_floor_alpha

    except FileNotFoundError:
        return tuple([None for _ in range(6)])


zero_floor_alpha, first_floor_alpha, second_floor_alpha, \
    third_floor_alpha, fourth_floor_alpha, fifth_floor_alpha = load_floor_schemas()

schedule = load_schedule()
