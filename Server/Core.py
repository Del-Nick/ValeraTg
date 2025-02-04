import asyncio
import datetime
from random import randint

from sqlalchemy import select, delete, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from Config.Config import global_settings
from Server.Models import Base, User, Settings, TgMessages, Homeworks, Books, Workshops, Exam
from Scripts.Others import get_sex_of_person_by_name

from aiogram.types import Message
from Config.Config import global_settings

engine, session_factory = global_settings.engine, global_settings.session_factory


class DB:
    @staticmethod
    async def create_tables():
        async with engine.begin() as conn:
            # await conn.run_sync(DeclarativeBase.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    @staticmethod
    async def select_manager(message: Message):
        user = await DB.select_user(TgID=message.chat.id)

        if not user:
            user = User(TgID=message.chat.id, TgName=message.chat.username)

            user.action = 'registration_get_vk_id'
            settings = Settings(ID=user.ID)
            user.settings = settings
            await DB.insert_user(user)

            user = await DB.select_user(TgID=message.chat.id)

        return user

    @staticmethod
    async def insert_user(user: User):
        async with session_factory() as session:
            session.add(user)
            await session.flush()

            session.add(user.settings)
            await session.flush()

            await session.commit()
            await engine.dispose()
            return user

    @staticmethod
    async def check_user_exists(VkID: int = None, TgID: int = None):
        async with session_factory() as session:
            query = select(User).where(User.TgID == TgID) if TgID else select(User).where(User.VkID == VkID)
            record_exist = bool((await session.execute(query)).first())
            await engine.dispose()
            return record_exist

    @staticmethod
    async def select_user(TgID: int = None, TgName: str = None) -> User | bool:
        """
        Получаем пользователя из БД. Если его нет возвращаем False
        :return: Объект User или False, если записи в БД нет
        """
        async with session_factory() as session:
            query = select(User).where(User.TgID == TgID) if TgID else select(User).where(User.TgName == TgName)
            record_exist = bool((await session.execute(query)).first())

            if record_exist:
                if TgID:
                    query = select(User).where(User.TgID == TgID).options(selectinload(User.settings))
                else:
                    query = select(User).where(User.TgName == TgName).options(selectinload(User.settings))

                result = await session.execute(query)
                user = result.scalars().all()[0]

                query = select(Settings).where(Settings.ID == user.ID)
                result = await session.execute(query)
                settings = result.scalars().one()

                user.settings = settings
                await engine.dispose()
                return user

            else:
                return False

    @staticmethod
    async def update_user(user: User):
        async with session_factory() as session:
            user_old = await session.get(User, user.ID)

            for key, value in user.__dict__.items():
                if key not in ('_sa_instance_state', 'settings'):
                    setattr(user_old, key, value)

            await session.commit()

            settings_old = await session.get(Settings, user.ID)

            for key, value in user.settings.__dict__.items():
                if key != '_sa_instance_state':
                    setattr(settings_old, key, value)

            await session.commit()
            await engine.dispose()

    @staticmethod
    async def merge_records(tg_user: User, VkID: int):
        async with session_factory() as session:
            query = select(User).where(User.VkID == VkID)
            result = await session.execute(query)
            vk_user = result.scalars().one()

            vk_user.TgID = tg_user.TgID
            vk_user.TgName = tg_user.TgName
            vk_user.first_conn = min(tg_user.first_conn, vk_user.first_conn)

            if vk_user.groups and tg_user.groups:
                vk_user.groups = [vk_user.groups[0]] + list(set(vk_user.groups[1:] + tg_user.groups[1:]))
            elif tg_user.groups:
                vk_user.groups = tg_user.groups

            await session.commit()

            query = delete(User).where(User.ID == tg_user.ID)
            await session.execute(query)

            await session.commit()
            await engine.dispose()

    @staticmethod
    async def delete_user(user: User):
        async with session_factory() as session:
            query = delete(User).where(User.ID == user.ID)
            await session.execute(query)

            await session.commit()
            await engine.dispose()

    @staticmethod
    async def insert_tg_messages(new_tg_message: TgMessages):
        async with session_factory() as session:
            session.add(new_tg_message)

            await session.flush()
            await session.commit()
            await engine.dispose()

    @staticmethod
    async def get_all_tg_names():
        async with session_factory() as session:
            query = text("""SELECT "TgName" FROM users where "TgName" IS NOT NULL""")
            result = await session.execute(query)
            return result.scalars().all()


class HomeworksDB:
    @staticmethod
    async def insert_homeworks(homeworks: Homeworks):
        async with session_factory() as session:
            session.add(homeworks)
            await session.commit()
            await engine.dispose()

    @staticmethod
    async def select_homeworks(group: str):
        async with session_factory() as session:
            query = select(Homeworks).where(Homeworks.group == group)
            record_exist = bool((await session.execute(query)).first())

        if record_exist:
            async with session_factory() as session:
                query = select(Homeworks).where(Homeworks.group == group)
                result = await session.execute(query)
                homeworks = result.scalars().one()

        else:
            homeworks = Homeworks(group=group)
            await HomeworksDB.insert_homeworks(homeworks)

            async with session_factory() as session:
                query = select(Homeworks).where(Homeworks.group == group)
                result = await session.execute(query)
                homeworks = result.scalars().one()

        await engine.dispose()
        return homeworks

    @staticmethod
    async def update_homeworks(homeworks: Homeworks):
        async with session_factory() as session:
            query = select(Homeworks).where(Homeworks.group == homeworks.group)
            result = await session.execute(query)
            homeworks_old = result.scalars().one()

            homeworks_old.homeworks = homeworks.homeworks

            await session.commit()
            await engine.dispose()


class BooksDB:
    @staticmethod
    async def insert_books(books: Books):
        async with session_factory() as session:
            session.add(books)
            await session.commit()
            await engine.dispose()

    @staticmethod
    async def select_books(course: str):
        async with session_factory() as session:
            query = select(Books).where(Books.course == course)
            record_exist = bool((await session.execute(query)).first())

        if record_exist:
            async with session_factory() as session:
                query = select(Books).where(Books.course == course)
                result = await session.execute(query)
                books = result.scalars().one()

        else:
            books = Books(course=course)
            await BooksDB.insert_books(books)

            async with session_factory() as session:
                query = select(Books).where(Books.course == course)
                result = await session.execute(query)
                books = result.scalars().one()

        await engine.dispose()
        return books

    @staticmethod
    async def update_books(books: Books):
        async with session_factory() as session:
            query = select(Books).where(Books.course == books.course)
            result = await session.execute(query)
            books_old = result.scalars().one()

            books_old.books = books.books

            await session.commit()
            await engine.dispose()

class WorkshopsDB:
    @staticmethod
    async def insert_workshops(workshops: Workshops):
        async with session_factory() as session:
            session.add(workshops)
            await session.commit()
            await engine.dispose()

    @staticmethod
    async def select_workshops(course: str):
        async with session_factory() as session:
            query = select(Workshops).where(Workshops.course == course)
            record_exist = bool((await session.execute(query)).first())

        if record_exist:
            async with session_factory() as session:
                query = select(Workshops).where(Workshops.course == course)
                result = await session.execute(query)
                workshops = result.scalars().one()

        else:
            workshops = Workshops(course=course)
            await WorkshopsDB.insert_workshops(workshops)

            async with session_factory() as session:
                query = select(Workshops).where(Workshops.course == course)
                result = await session.execute(query)
                workshops = result.scalars().one()

        return workshops

    @staticmethod
    async def update_workshops(workshops: Workshops):
        async with session_factory() as session:
            query = select(Workshops).where(Workshops.course == workshops.course)
            result = await session.execute(query)
            workshops_old = result.scalars().one()

            workshops_old.workshops = workshops.workshops

            await session.commit()
            await engine.dispose()


class SessionDB:
    @staticmethod
    async def insert(exam: Exam):
        async with session_factory() as session:
            session.add(exam)
            await session.commit()
            await engine.dispose()

    @staticmethod
    async def select(group: str):
        async with session_factory() as session:
            query = select(Exam).filter(Exam.group == group).order_by(Exam.exam_datetime)
            result = await session.execute(query)
            exams = result.scalars().all()
            await engine.dispose()
            return exams

    @staticmethod
    async def update(exam: Exam):
        async with session_factory() as session:
            query = select(Exam).filter(Exam.group == exam.group, Exam.name == exam.name)
            result = await session.execute(query)
            exam_old = result.scalars().one()

            exam_old.teacher = exam.teacher
            exam_old.exam_datetime = exam.exam_datetime
            exam_old.room = exam.room

            await session.commit()
            await engine.dispose()