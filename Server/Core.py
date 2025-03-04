import traceback
from typing import List

from aiogram.types import Message
from sqlalchemy import select, delete, text
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert

from Config.Config import global_settings
from Server.Models import Base, User, Settings, TgMessages, Homeworks, Books, Workshops, Exam, Quiz, QuizUser, \
    GroupName, Lesson, WeekType, CustomLesson

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
            return user

    @staticmethod
    async def check_user_exists(VkID: int = None, TgID: int = None):
        async with session_factory() as session:
            query = select(User).where(User.TgID == TgID) if TgID else select(User).where(User.VkID == VkID)
            record_exist = bool((await session.execute(query)).first())

            return record_exist

    @staticmethod
    async def select_user(TgID: int = None, TgName: str = None, user_id: int = None) -> User | bool:
        """
        Получаем пользователя из БД. Если его нет возвращаем False
        :return: Объект User или False, если записи в БД нет
        """
        async with session_factory() as session:
            if TgID:
                query = select(User).where(User.TgID == TgID)
            elif TgName:
                query = select(User).where(User.TgName == TgName)
            else:
                query = select(User).where(User.ID == user_id)
            record_exist = bool((await session.execute(query)).first())

            if record_exist:
                if TgID:
                    query = select(User).where(User.TgID == TgID).options(selectinload(User.settings))
                elif TgName:
                    query = select(User).where(User.TgName == TgName).options(selectinload(User.settings))
                else:
                    query = select(User).where(User.ID == user_id).options(selectinload(User.settings))

                result = await session.execute(query)
                user = result.scalars().all()[0]

                query = select(Settings).where(Settings.ID == user.ID)
                result = await session.execute(query)
                settings = result.scalars().one()

                user.settings = settings
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

    @staticmethod
    async def delete_user(user: User):
        async with session_factory() as session:
            query = delete(User).where(User.ID == user.ID)
            await session.execute(query)

            await session.commit()

    @staticmethod
    async def insert_tg_messages(new_tg_message: TgMessages):
        async with session_factory() as session:
            session.add(new_tg_message)

            await session.flush()
            await session.commit()

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

        return homeworks

    @staticmethod
    async def update_homeworks(homeworks: Homeworks):
        async with session_factory() as session:
            query = select(Homeworks).where(Homeworks.group == homeworks.group)
            result = await session.execute(query)
            homeworks_old = result.scalars().one()

            homeworks_old.homeworks = homeworks.homeworks
            await session.commit()


class BooksDB:
    @staticmethod
    async def insert_books(books: Books):
        async with session_factory() as session:
            session.add(books)
            await session.commit()

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

        return books

    @staticmethod
    async def update_books(books: Books):
        async with session_factory() as session:
            query = select(Books).where(Books.course == books.course)
            result = await session.execute(query)
            books_old = result.scalars().one()

            books_old.books = books.books

            await session.commit()


class WorkshopsDB:
    @staticmethod
    async def insert_workshops(workshops: Workshops):
        async with session_factory() as session:
            session.add(workshops)
            await session.commit()

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


class SessionDB:
    @staticmethod
    async def insert(exam: Exam):
        async with session_factory() as session:
            session.add(exam)
            await session.commit()

    @staticmethod
    async def select(group: str):
        async with session_factory() as session:
            query = select(Exam).filter(Exam.group == group).order_by(Exam.exam_datetime)
            result = await session.execute(query)
            exams = result.scalars().all()

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


class QuizDB:
    @staticmethod
    async def create_table():
        async with engine.begin() as conn:
            await conn.run_sync(Quiz.__table__.create)

    @staticmethod
    async def insert(question: Quiz):
        async with session_factory() as session:
            session.add(question)
            await session.commit()

    @staticmethod
    async def select(num: int) -> Quiz:
        async with session_factory() as session:
            query = select(Quiz).where(Quiz.id == num)
            result = await session.execute(query)
            question = result.scalars().one()

            return question

    @staticmethod
    async def update(question: Quiz):
        async with session_factory() as session:
            query = select(Quiz).where(Quiz.id == question.id)
            result = await session.execute(query)
            question_old = result.scalars().one()

            question_old.question = question.question
            question_old.variants = question.variants
            question_old.answer = question.answer
            question_old.desc = question.desc

            await session.commit()


class QuizUserDB:
    @staticmethod
    async def create_table():
        async with engine.begin() as conn:
            await conn.run_sync(QuizUser.__table__.create)

    @staticmethod
    async def insert(quiz_user: QuizUser):
        async with session_factory() as session:
            session.add(quiz_user)
            await session.commit()

    @staticmethod
    async def select(user_id: int) -> QuizUser:
        async with session_factory() as session:
            query = select(QuizUser).where(QuizUser.user_id == user_id)
            result = await session.execute(query)
            quiz_user = result.scalars().one_or_none()

            return quiz_user

    @staticmethod
    async def select_all_users() -> List[QuizUser]:
        async with session_factory() as session:
            query = select(QuizUser)
            result = await session.execute(query)
            quiz_users = result.scalars().all()
            return quiz_users

    @staticmethod
    async def update(quiz_user: QuizUser):
        async with session_factory() as session:
            query = select(QuizUser).where(QuizUser.id == quiz_user.id)
            result = await session.execute(query)
            quiz_user_old = result.scalars().one()

            quiz_user_old.count_true_answers = quiz_user.count_true_answers

            if quiz_user.end_datetime:
                quiz_user_old.end_datetime = quiz_user.end_datetime

            await session.commit()


class GroupNameDB:
    @staticmethod
    async def create_table():
        async with engine.begin() as conn:
            await conn.run_sync(GroupName.__table__.create)

    @staticmethod
    async def insert(group: GroupName = None, groups: list[GroupName] = None):
        async with session_factory() as session:
            session.add_all(groups) if groups else session.add(group)
            await session.commit()

    @staticmethod
    async def select(group_name: str) -> GroupName:
        async with session_factory() as session:
            query = select(GroupName).where(GroupName.group_name == group_name)
            result = await session.execute(query)
            group = result.scalars().one_or_none()

            return group


class LessonScheduleDB:
    @staticmethod
    async def create_table():
        async with engine.begin() as conn:
            await conn.run_sync(Lesson.__table__.create)

    @staticmethod
    async def update_or_insert_list_lessons(lessons: list[tuple[Lesson, str]] = None):
        async with (session_factory() as session):
            groups = (await session.execute(select(GroupName))).scalars().all()

            db_groups_names = set([g.group_name for g in groups])
            schedule_groups_names = set(x[1] for x in lessons)

            if len(schedule_groups_names - db_groups_names) > 0:
                expected_groups = list(schedule_groups_names - db_groups_names)
                await GroupNameDB.insert(groups=[GroupName(group_name=g) for g in expected_groups])
                groups = (await session.execute(select(GroupName))).scalars().all()

            groups = {g.group_name: g.id for g in groups}

            try:
                lessons_data = [lesson.get_dict_values(group_id=groups[group_name]) for lesson, group_name in lessons]

                query = insert(Lesson).values(lessons_data)
                query = query.on_conflict_do_update(constraint='uq_schedule_unique_lesson',
                                                    set_={
                                                        "lesson": query.excluded.lesson,
                                                        "teacher": query.excluded.teacher,
                                                        "room": query.excluded.room
                                                    })
                await session.execute(query)
                await session.commit()

            except KeyError:
                traceback.print_exc()
                await session.close()

    @staticmethod
    async def update_or_insert_one_lesson(lesson: Lesson, group_name: str):
        async with (session_factory() as session):
            group = (await session.execute(
                select(GroupName).where(GroupName.group_name == group_name))).scalars().one_or_none()

            if group:
                lesson_data = lesson.get_dict_values(group_id=group.id)
                query = insert(Lesson).values(lesson_data)
                query = query.on_conflict_do_update(constraint='uq_schedule_unique_lesson',
                                                    set_={
                                                        "lesson": query.excluded.lesson,
                                                        "teacher": query.excluded.teacher,
                                                        "room": query.excluded.room
                                                    })
                await session.execute(query)
                await session.commit()

            else:
                await session.close()

    @staticmethod
    async def select(group_name: str, weekday: int, week_type: WeekType = None) -> list[Lesson] | None:
        async with (session_factory() as session):
            group = await GroupNameDB.select(group_name=group_name)
            if group:
                query = select(Lesson).where(Lesson.group_id == group.id, Lesson.weekday == weekday
                                             ).order_by(Lesson.lesson_number, Lesson.week_type)
                if week_type:
                    query = select(Lesson).where(Lesson.group_id == group.id, Lesson.weekday == weekday,
                                                 Lesson.week_type == week_type,
                                                 ).order_by(Lesson.lesson_number, Lesson.week_type)
                else:
                    query = select(Lesson).where(Lesson.group_id == group.id, Lesson.weekday == weekday
                                                 ).order_by(Lesson.lesson_number, Lesson.week_type)

                result = await session.execute(query)
                lessons = result.scalars().all()
                return lessons[0] if type(lessons) is tuple else lessons

            else:
                await session.close()

    @staticmethod
    async def select_one_lesson(group_name: str, weekday: int, lesson_number: int,
                                week_type: WeekType = None) -> Lesson:
        async with session_factory() as session:
            group = await GroupNameDB.select(group_name=group_name)

            query = select(Lesson).where(Lesson.group_id == group.id,
                                         Lesson.weekday == weekday,
                                         Lesson.lesson_number == lesson_number,
                                         Lesson.week_type == week_type)

            result = await session.execute(query)
            lesson = result.scalars().one_or_none()

            return lesson


class CustomLessonScheduleDB:
    @staticmethod
    async def create_table():
        async with engine.begin() as conn:
            await conn.run_sync(CustomLesson.__table__.create)

    @staticmethod
    async def update_or_insert_one_lesson(lesson: CustomLesson, group_name: str):
        async with (session_factory() as session):
            group = (await session.execute(
                select(GroupName).where(GroupName.group_name == group_name))).scalars().one_or_none()

            if group:
                lesson_data = lesson.get_dict_values(group_id=group.id)
                query = insert(CustomLesson).values(lesson_data)
                query = query.on_conflict_do_update(constraint='uq_custom_schedule_unique_lesson',
                                                    set_={
                                                        "lesson": query.excluded.lesson,
                                                        "teacher": query.excluded.teacher,
                                                        "room": query.excluded.room
                                                    })
                await session.execute(query)
                await session.commit()

            else:
                await session.close()

    @staticmethod
    async def select(group_name: str, weekday: int, week_type: WeekType) -> list[CustomLesson] | None:
        async with session_factory() as session:
            group = await GroupNameDB.select(group_name=group_name)
            if group:

                if week_type:
                    query = select(CustomLesson).where(CustomLesson.group_id == group.id,
                                                       CustomLesson.weekday == weekday,
                                                       CustomLesson.week_type == week_type
                                                       ).order_by(CustomLesson.week_type, CustomLesson.lesson_number)
                else:
                    query = select(CustomLesson).where(CustomLesson.group_id == group.id,
                                                       CustomLesson.weekday == weekday
                                                       ).order_by(CustomLesson.week_type, CustomLesson.lesson_number)

                result = await session.execute(query)
                lessons = result.scalars().all()

                return lessons[0] if type(lessons) is tuple else lessons

            else:
                await session.close()

    @staticmethod
    async def select_one_lesson(group_name: str, weekday: int, lesson_number: int,
                                week_type: WeekType = None) -> List[CustomLesson]:
        async with session_factory() as session:
            group = await GroupNameDB.select(group_name=group_name)
            query = select(CustomLesson).where(CustomLesson.group_id == group.id,
                                               CustomLesson.weekday == weekday,
                                               CustomLesson.lesson_number == lesson_number,
                                               CustomLesson.week_type == week_type)

            result = await session.execute(query)
            lessons = result.scalars().one_or_none()

            return lessons
