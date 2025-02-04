from datetime import datetime, time
from typing import Annotated, List, Type

from sqlalchemy import String, ForeignKey, Column, DateTime, Time, JSON, select, BigInteger, update
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, relationship
from sqlalchemy.sql import func

from Config.Config import global_settings

first_conn_form = Annotated[datetime, mapped_column(server_default=func.now())]
last_conn_form = Annotated[datetime, mapped_column(server_default=func.now(), onupdate=func.now())]
intpk = Annotated[int, mapped_column(primary_key=True)]

engine, session_factory = global_settings.engine, global_settings.session_factory


class Base(DeclarativeBase):
    def __repr__(self):

        user_fields = [f'{key}: {value}' for key, value in self.__dict__.items() if key not in ('_sa_instance_state', 'settings')]
        settings_fields = [f'{key}: {value}' for key, value in self.settings.__dict__.items() if key != '_sa_instance_state']
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
