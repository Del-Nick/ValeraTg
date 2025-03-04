from datetime import datetime, time
from enum import Enum as PyEnum
from typing import Annotated, List, Type

from sqlalchemy import String, ForeignKey, Column, DateTime, Time, JSON, select, BigInteger, update, \
    UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, ENUM
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, relationship
from sqlalchemy.sql import func

from Config.Config import global_settings

first_conn_form = Annotated[datetime, mapped_column(server_default=func.now())]
last_conn_form = Annotated[datetime, mapped_column(server_default=func.now(), onupdate=func.now())]
intpk = Annotated[int, mapped_column(primary_key=True)]


class WeekType(PyEnum):
    EVEN = 'even'
    ODD = 'odd'


week_enum = ENUM(WeekType, name="week_type", create_type=False)


engine, session_factory = global_settings.engine, global_settings.session_factory


class Base(DeclarativeBase):
    def __repr__(self):
        user_fields = [f'{key}: {value}' for key, value in self.__dict__.items() if
                       key not in ('_sa_instance_state', 'settings')]
        settings_fields = [f'{key}: {value}' for key, value in self.settings.__dict__.items() if
                           key != '_sa_instance_state']
        return (f'USER      --> {'\n              '.join(user_fields)}\n'
                f'SETTINGS  --> {'\n              '.join(settings_fields)}')


class User(Base):
    __tablename__ = 'users'

    ID: Mapped[intpk]
    VkID = Column(BigInteger)
    VkFirstName: Mapped[str | None] = mapped_column(String(20))
    VkLastName: Mapped[str | None] = mapped_column(String(20))
    TgID = Column(BigInteger)
    TgName: Mapped[str | None] = mapped_column(String(30))
    sex: Mapped[str | None] = mapped_column(String(1))
    first_conn: Mapped[datetime] = Column(DateTime, default=func.now())
    last_conn: Mapped[datetime] = Column(DateTime, default=func.now(), onupdate=func.now())
    groups = Column(ARRAY(String))
    action: Mapped[str | None] = mapped_column(String(255), default='start_menu')

    settings: Mapped['Settings'] = relationship(backref='user')

    def __init__(self, VkID: int = None, VkFirstName: str = None, VkLastName: str = None, TgID: int = None,
                 TgName: str = None, sex: str = None, groups: list = None, action: str = None):
        self.VkID = VkID
        self.VkFirstName = VkFirstName
        self.VkLastName = VkLastName
        self.TgID = TgID
        self.TgName = TgName
        self.sex = sex
        self.groups = groups
        self.action = action


class Settings(Base):
    __tablename__ = 'settings'

    ID: Mapped[intpk] = mapped_column(ForeignKey('users.ID'))
    full_schedule: Mapped[bool] = mapped_column(default=False)
    notifications: Mapped[bool] = mapped_column(default=False)
    schedule_seller: Mapped[bool] = mapped_column(default=False)
    tomorrow_schedule_after: Mapped[time] = Column(Time, default=time(hour=18))
    headman: Mapped[bool] = mapped_column(default=False)
    studsovet: Mapped[bool] = mapped_column(default=False)
    admin: Mapped[bool] = mapped_column(default=False)
    schedule_mailing_time: Mapped[time] = Column(Time, default=time(hour=8))
    pause: Mapped[bool] = mapped_column(default=False)

    def __init__(self, ID: int):
        self.ID = ID


class TgMessages(Base):
    __tablename__ = 'TgMessages'

    id: Mapped[intpk]
    time: Mapped[datetime] = Column(DateTime, default=func.now())
    TgName: Mapped[str]
    action: Mapped[str]
    type_action: Mapped[str]

    def __init__(self, TgName: str, action: str, type_action: str):
        self.TgName = TgName
        self.action = action
        self.type_action = type_action


class Books(Base):
    __tablename__ = 'books'

    course: Mapped[str] = Column(primary_key=True)
    books = Column(JSON)

    def __init__(self, course: str):
        self.course = course

    def __repr__(self):
        return (f'Курс:       {self.course}\n'
                f'Учебники:   {self.books}')


class Homeworks(Base):
    __tablename__ = 'homeworks'

    group: Mapped[str] = Column(primary_key=True)
    homeworks = Column(JSON)

    def __init__(self, group: str):
        self.group = group


class Workshops(Base):
    __tablename__ = 'workshops'

    course: Mapped[str] = Column(primary_key=True)
    workshops = Column(JSON)

    def __init__(self, course: str):
        self.course = course


class Exam(Base):
    __tablename__ = 'session'

    id: Mapped[intpk]
    group: Mapped[str]
    name: Mapped[str]
    teacher: Mapped[str]
    exam_datetime: Mapped[datetime]
    room: Mapped[str]

    def __repr__(self):
        return f'{self.group}   {self.name}    {self.teacher}  {self.exam_datetime}    {self.room}'


class Quiz(Base):
    __tablename__ = 'quiz'

    id: Mapped[intpk]
    question: Mapped[str]
    variants = Column(JSON)
    answer: Mapped[str]
    desc: Mapped[str]

    def __repr__(self):
        return (f'{self.id}.ВОПРОС:    {self.answer}\n\n'
                f'ВАРИАНТЫ:     {self.variants}\n'
                f'ОТВЕТ:    {self.answer}\n\n'
                f'ОПИСАНИЕ:     {self.desc}\n\n')

    def __init__(self, question: str, variants: list, answer: str, desc: str):
        super().__init__()
        self.question = question
        self.variants = variants
        self.answer = answer
        self.desc = desc


class QuizUser(Base):
    __tablename__ = 'quiz_user'

    id: Mapped[intpk]
    user_id: Mapped[int]
    count_true_answers: Mapped[int] = mapped_column(default=0)
    start_datetime: Mapped[datetime] = Column(DateTime, default=func.now())
    end_datetime: Mapped[datetime]


class GroupName(Base):
    __tablename__ = 'groups_names'

    id: Mapped[intpk]
    group_name: Mapped[str] = Column(String(), nullable=False, unique=True)


class Lesson(Base):
    __tablename__ = 'lessons_schedule'
    __table_args__ = (
        UniqueConstraint('group_id', 'weekday', 'lesson_number', 'week_type', name='uq_schedule_unique_lesson'),
    )

    id: Mapped[intpk]
    group_id: Mapped[int] = Column(ForeignKey(GroupName.id))
    weekday: Mapped[int]
    lesson_number: Mapped[int]
    week_type = Column(week_enum, nullable=False)
    lesson: Mapped[str]
    teacher = Column(String(), nullable=True)
    room = Column(String(), nullable=True)

    group = relationship(GroupName, backref='schedules')

    def __repr__(self):
        return (f'Группа: {self.group_id}  День недели: {self.weekday}  Неделя: {'нечётная' if self.week_type == WeekType.ODD else 'чётная'}\n'
                f'  Пара: {self.lesson_number}\n'
                f'      Предмет:    {self.lesson}\n'
                f'      Препод:     {self.teacher}\n'
                f'      Кабинет:    {self.room}\n')

    def get_dict_values(self, group_id: int):
        return {'group_id': group_id,
                'weekday': self.weekday,
                'lesson_number': self.lesson_number,
                'week_type': self.week_type,
                'lesson': self.lesson,
                'teacher': self.teacher,
                'room': self.room}


class CustomLesson(Base):
    __tablename__ = 'custom_lessons_schedule'
    __table_args__ = (
        UniqueConstraint('group_id', 'weekday', 'lesson_number', 'week_type',
                         name='uq_custom_schedule_unique_lesson'),
    )

    id: Mapped[intpk]
    group_id: Mapped[int] = Column(ForeignKey(GroupName.id))
    weekday: Mapped[int]
    lesson_number: Mapped[int]
    week_type = Column(week_enum, nullable=False)
    lesson: Mapped[str]
    teacher = Column(String(), nullable=True)
    room = Column(String(), nullable=True)

    def __repr__(self):
        return (f'Группа: {self.group_id}  День недели: {self.weekday}  Неделя: {'нечётная' if self.week_type == WeekType.ODD else 'чётная'}\n'
                f'  Пара: {self.lesson_number}\n'
                f'      Предмет:    {self.lesson}\n'
                f'      Препод:     {self.teacher}\n'
                f'      Кабинет:    {self.room}\n')

    def get_dict_values(self, group_id: int):
        return {'group_id': group_id,
                'weekday': self.weekday,
                'lesson_number': self.lesson_number,
                'week_type': self.week_type,
                'lesson': self.lesson,
                'teacher': self.teacher,
                'room': self.room}
