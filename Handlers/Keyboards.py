import datetime

from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder, KeyboardBuilder
from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
import dataclasses

from Server.Models import User


@dataclasses.dataclass
class Buttons:
    homeworks: InlineKeyboardButton = InlineKeyboardButton(text='📝 ДЗ', callback_data='start_homeworks')
    books: InlineKeyboardButton = InlineKeyboardButton(text='📚 Учебники', callback_data='start_books')
    workshops: InlineKeyboardButton = InlineKeyboardButton(text='🔬 Праки', callback_data='start_workshops_main')

    schedule: InlineKeyboardButton = InlineKeyboardButton(text='📆 Расписание', callback_data='start_schedule')
    # schedule: InlineKeyboardButton = InlineKeyboardButton(text='📆 Сессия', callback_data='start_session')

    settings: InlineKeyboardButton = InlineKeyboardButton(text='⚙ Настройки', callback_data='settings_main')
    headman: InlineKeyboardButton = InlineKeyboardButton(text='😎 Староста Mode', callback_data='headman_main')

    admin: InlineKeyboardButton = InlineKeyboardButton(text='Админ панель', callback_data='admin_start')

    no: KeyboardButton = KeyboardButton(text='❌ Нет')
    yes: KeyboardButton = KeyboardButton(text='✅ Да')

    no_group: KeyboardButton = KeyboardButton(text='Нет нужной группы')
    not_student: KeyboardButton = KeyboardButton(text='Я не студент физфака')

    later: KeyboardButton = KeyboardButton(text='Напишу позже')


@dataclasses.dataclass
class Weekdays:
    mon: InlineKeyboardButton = InlineKeyboardButton(text='ПН', callback_data=f'start_schedule_day=0')
    tue: InlineKeyboardButton = InlineKeyboardButton(text='ВТ', callback_data=f'start_schedule_day=1')
    wed: InlineKeyboardButton = InlineKeyboardButton(text='СР', callback_data=f'start_schedule_day=2')
    thu: InlineKeyboardButton = InlineKeyboardButton(text='ЧТ', callback_data=f'start_schedule_day=3')
    fri: InlineKeyboardButton = InlineKeyboardButton(text='ПТ', callback_data=f'start_schedule_day=4')
    sat: InlineKeyboardButton = InlineKeyboardButton(text='СБ', callback_data=f'start_schedule_day=5')

    def __init__(self, group: str = None):
        if group:
            self.mon = InlineKeyboardButton(text='ПН', callback_data=f'start_schedule_day=0_group={group}')
            self.tue = InlineKeyboardButton(text='ВТ', callback_data=f'start_schedule_day=1_group={group}')
            self.wed = InlineKeyboardButton(text='СР', callback_data=f'start_schedule_day=2_group={group}')
            self.thu = InlineKeyboardButton(text='ЧТ', callback_data=f'start_schedule_day=3_group={group}')
            self.fri = InlineKeyboardButton(text='ПТ', callback_data=f'start_schedule_day=4_group={group}')
            self.sat = InlineKeyboardButton(text='СБ', callback_data=f'start_schedule_day=5_group={group}')


def standard_keyboard(user: User):
    keyboard = InlineKeyboardBuilder()

    group = user.groups[0]
    b = Buttons()

    if len(group) == 3 and int(group[0]) < 4:
        keyboard.row(b.homeworks, b.books, b.workshops)
    else:
        keyboard.row(b.homeworks, b.books)

    keyboard.row(b.schedule)

    if user.settings.headman:
        keyboard.row(b.settings, b.headman)
    else:
        keyboard.row(b.settings)

    if user.settings.admin:
        keyboard.row(b.admin)

    return keyboard


def later_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[Buttons.later]], resize_keyboard=True)


def yes_no_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text='Нет', callback_data='registration_help_no'),
                 InlineKeyboardButton(text='Да', callback_data='registration_help_yes'))
    return keyboard


def cancel_keyboard_usual():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='Отмена')]], resize_keyboard=True)


# TODO: переписать на callback!!
def groups_keyboard(main_part_callback: str, groups: list) -> InlineKeyboardBuilder:
    """
    Возвращает клавиатуру с группами, похожими на запрос пользователя
    :param main_part_callback: Callback формируется по образцу {main_part_callback}={group}
    :param groups: Список названий групп
    :return: Объект клавиатуры
    """
    keyboard = InlineKeyboardBuilder()
    for group in groups:
        keyboard.button(text=group, callback_data=f'{main_part_callback}={group}')

    keyboard.row(InlineKeyboardButton(text='Нет нужной группы',
                                      callback_data=f'{main_part_callback}=no_exist'))

    return keyboard


def groups_to_delete_keyboard(groups) -> KeyboardBuilder[InlineKeyboardButton]:
    keyboard = InlineKeyboardBuilder()
    for i, group in enumerate(groups):
        groups[i] = InlineKeyboardButton(text=group, callback_data=f'settings_delete_group={group}')

    return keyboard.row(*groups)


def not_student_keyboard(main_callback_part: str) -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()
    return keyboard.button(text='Я не студент физфака',
                           callback_data=f'{main_callback_part}=not_student')


def empty_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def schedule_keyboard(user: User, group: str, day: int = None) -> InlineKeyboardBuilder:
    keyboard = InlineKeyboardBuilder()

    if day is not None:
        weekdays = Weekdays(group) if group != user.groups[0] else Weekdays()
        weekdays = [weekdays.mon, weekdays.tue, weekdays.wed, weekdays.thu, weekdays.fri, weekdays.sat]

        del weekdays[day]

        keyboard.row(*weekdays)

    day = day if day else datetime.datetime.now().day

    if len(user.groups) > 1:
        groups = []
        if group != user.groups[0]:
            groups.append(InlineKeyboardButton(text=user.groups[0], callback_data=f'start_schedule_day={day}'))

        for user_group in user.groups[1:]:
            if group != user_group:
                groups.append(InlineKeyboardButton(text=user_group,
                                                   callback_data=f'start_schedule_day={day}_group={user_group}'))

        keyboard.row(*groups)

    elif group != user.groups[0]:
        keyboard.row(InlineKeyboardButton(text=user.groups[0], callback_data=f'start_schedule_day={day}'))

    keyboard.row(InlineKeyboardButton(text='Ввести другую группу', callback_data='start_schedule_get_custom_group'))
    keyboard.row(InlineKeyboardButton(text='Сообщить об ошибке', callback_data='start_get_error'))
    keyboard.row(InlineKeyboardButton(text='Назад', callback_data='start_menu'))

    return keyboard


@dataclasses.dataclass
class SettingsActions:
    settings: str = 'settings'
    main: str = 'main'
    get_schedule_time: str = 'get_schedule_time'
    change_main_group: str = 'change_main_group'

    delete_group: str = 'delete_group'
    add_group: str = 'add_group'

    change_full_schedule: str = 'change_full_schedule'
    change_notifications: str = 'change_notifications'
    get_new_main_group_alert_sent: str = 'get_new_main_group_alert_sent'
    get_time_for_schedule_sender: str = 'get_time_for_schedule_sender'
    get_vk_id: str = 'get_vk_id'

    @staticmethod
    def joiner(method: str) -> str:
        return f'settings_{method}'


def settings_keyboard(user: User):
    keyboard = InlineKeyboardBuilder()

    acts = SettingsActions()

    keyboard.row(InlineKeyboardButton(
        text=f'🕒 Время: {user.settings.tomorrow_schedule_after.strftime("%H:%M")}',
        callback_data=acts.joiner(acts.get_schedule_time)),
        InlineKeyboardButton(
            text='🔄 Сменить группу',
            callback_data=acts.joiner(acts.change_main_group)))

    keyboard.row(InlineKeyboardButton(
        text=f'Удалить группу',
        callback_data=acts.joiner(acts.delete_group)),
        InlineKeyboardButton(
            text='Добавить группу',
            callback_data=acts.joiner(acts.add_group)))

    if user.settings.full_schedule:
        full_schedule = InlineKeyboardButton(text='Всё расписание: ✅',
                                             callback_data=acts.joiner(acts.change_full_schedule))
    else:
        full_schedule = InlineKeyboardButton(text='Всё расписание: ☑',
                                             callback_data=acts.joiner(acts.change_full_schedule))

    if user.settings.notifications:
        notifications = InlineKeyboardButton(text='Уведомления: ✅',
                                             callback_data=acts.joiner(acts.change_notifications))
    else:
        notifications = InlineKeyboardButton(text='Уведомления: ☑',
                                             callback_data=acts.joiner(acts.change_notifications))

    keyboard.row(full_schedule, notifications)

    if not user.VkID:
        keyboard.row(InlineKeyboardButton(text='Добавить VkID',
                                          callback_data=acts.joiner(acts.get_vk_id)))

    keyboard.row(InlineKeyboardButton(text='Назад',
                                      callback_data='start_menu'))

    return keyboard


def custom_keyboard(callback_back_button,
                    main_callback: str = None,
                    buttons: list[tuple[str, str]] = None,
                    buttons_in_row: int = 2) -> InlineKeyboardBuilder:
    """
    Шаблон для создания произвольной клавиатуры
    :param buttons_in_row: Количество кнопок в строке клавиатуры
    :param main_callback: Основная часть CallbackQuery, с которой она начинается
    :param buttons: Список кортежей с данными кнопки в формате (Текст, CallbackData)
    :param callback_back_button: CallbackData для кнопки Назад
    :return: Объект клавиатуры
    """
    keyboard = InlineKeyboardBuilder()

    if buttons:
        for button in buttons:
            keyboard.button(text=button[0],
                            callback_data=f'{main_callback}_{button[1]}')

        keyboard.adjust(buttons_in_row)

    keyboard.row(InlineKeyboardButton(text='Назад',
                                      callback_data=callback_back_button))

    return keyboard
