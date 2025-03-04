import asyncio
import random
from dataclasses import dataclass
from datetime import datetime

from aiogram import Bot
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder, KeyboardBuilder
from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.exceptions import TelegramRetryAfter

from Server.Core import QuizDB, QuizUserDB
from Server.Models import User, Quiz, QuizUser


class Keyboards:
    @staticmethod
    def main_keyboard(user: User):
        keyboard = InlineKeyboardBuilder()

        main: InlineKeyboardButton = InlineKeyboardButton(text='🤯  КВИЗ  🤯', callback_data='event_quiz')
        back: InlineKeyboardButton = InlineKeyboardButton(text='Назад', callback_data='start_menu')

        keyboard.row(main)
        keyboard.row(back)

        return keyboard

    @staticmethod
    def start_quiz_keyboard():
        keyboard = InlineKeyboardBuilder()

        start: InlineKeyboardButton = InlineKeyboardButton(text='Конечно!', callback_data='event_quiz_started')
        back: InlineKeyboardButton = InlineKeyboardButton(text='Назад', callback_data='event')

        keyboard.row(start)
        keyboard.row(back)

        return keyboard

    @staticmethod
    def quiz_keyboard(question: Quiz):
        keyboard = InlineKeyboardBuilder()

        vars = question.variants
        random.shuffle(vars)

        [keyboard.row(
            InlineKeyboardButton(text=var, callback_data=f'event_quiz_started?num={question.id}&answer={var[:10]}'))
            for var in vars]
        return keyboard


wrong_answers = ['Неверно, но не отчаивайся: каждая попытка — это маленькое приключение!',
                 'Неверно, но это просто ещё одна возможность узнать что-то новое',
                 'Не совсем так',
                 'Ну, почти']

wrong_stickers = ['CAACAgIAAxkBAAENuihnpJtyCfup6YI8blUccjPiqEikyAACJwADWbv8JYdlBkQXVYX4NgQ',
                  'CAACAgIAAxkBAAENs8JnoICwoeiuCdBlf4x4tqCfOKnYygACfQAD9wLIDy7JuwrdyyJJNgQ',
                  'CAACAgIAAxkBAAENui5npJvdwaOi3lKIYvWzDzDFk9dSugACgwADFjlICdOOLkodWm3jNgQ',
                  'CAACAgIAAxkBAAENs8BnoICOGw9UvyJCDc3wHTs6nwe3wQACDwwAAuKOOUotFzfMTUK3UDYE']

true_answers = ['Да, в точку!',
                'Зришь в корень!',
                'Кто понял жизнь, тот не спешит']

true_stickers = ['CAACAgIAAxkBAAENuipnpJuE3iPnTgmd878Il6V4W9mZbAACkAADFjlICTxLOubV642ONgQ',
                 'CAACAgIAAxkBAAENujJnpJwPEXJaIelCDnBpOfwefsUbzwACngAD9wLIDxjzyiQZP6pbNgQ',
                 'CAACAgIAAxkBAAENujRnpJwkyeXCoEEqFInekBNPNi4XhwACGgAD9wLID68vCWlyjjbLNgQ',
                 'CAACAgIAAxkBAAENujZnpJw57nH2ytPcZiAX1S2sBgM6NAACjQADFjlICdDOryXD7AkyNgQ']

event_schedule = ('Приглашаем вас посетить мероприятия, приуроченные ко Дню российской науки.\n\n'
                  ''
                  '          *7 февраля:*\n\n'
                  '*12³⁰ - 14⁰⁰* — круглый стол с учёными физфака "Физиком становятся" в СФА\n'
                  '*14⁰⁰ - 15²⁰* — Мастер-класс "Оформи стендовый доклад", физическая настольная '
                  'игра "AliaScience" и кофе-брейк в холле ЦФА\n'
                  '*15²⁰ - 16⁵⁵* — Лекция от "Лаборатории Касперского" в СФА\n\n\n'
                  ''
                  '          *12 февраля:*\n\n'
                  '🔹"Научный бой" между факультетами в коворкинге 1 ГУМа\n'
                  '🔹Экскурсии в научно-исследовательские центры и компании - даты уточняются\n'
                  '🔹Посещение лабораторий и кафедр физического факультета - даты уточняются')


async def event_handler(bot: Bot, user: User, callback: CallbackQuery = None):
    if callback.data == 'event':
        user.action = 'event'
        await callback.message.edit_text(
            text=event_schedule,
            reply_markup=Keyboards.main_keyboard(user).as_markup(),
            parse_mode='Markdown')

    elif callback.data == 'event_quiz':
        quiz_user = await QuizUserDB.select(user_id=user.ID)

        if quiz_user:
            await callback.message.answer_animation(
                animation='CAACAgIAAxkBAAENuydnpTiNzWS2IdnMrurDoD893rBJZQACcAAD9wLIDyQpDCtech2jNgQ'
            )
            await callback.message.edit_text(text=f'Поздравляю! Твой результат {quiz_user.count_true_answers} из 11 '
                                                  f'вопросов! На прохождение ушло '
                                                  f'{(quiz_user.end_datetime - quiz_user.start_datetime).total_seconds():.1f} c')
            await callback.message.answer(text=event_schedule,
                                          reply_markup=Keyboards.main_keyboard(user).as_markup(),
                                          parse_mode='Markdown')

        else:
            user.action = 'event_quiz'
            await callback.message.edit_text(
                text='Рады приветствовать тебя на этой викторине. Впереди тебя ждут 11 вопросов из разных областей. \n\n'
                     'За хорошие ответы ты *получишь призы*, но играй честно, не подглядывай и не говори ответы другим '
                     'участникам. Давай не портить впечатления от игры.\n\n'
                     ''
                     'Небольшое уточнение. После начала викторины ты *не сможешь вернуться в основное меню*, пока не '
                     'закончишь её. Начинаем?',
                reply_markup=Keyboards.start_quiz_keyboard().as_markup(),
                parse_mode='Markdown'
            )

    elif callback.data == 'event_quiz_started':
        user.action = 'event_quiz_started'
        question = await QuizDB.select(num=1)
        await callback.message.edit_text(text=question.question,
                                         reply_markup=Keyboards.quiz_keyboard(question).as_markup(),
                                         parse_mode='Markdown')
        await QuizUserDB.insert(QuizUser(user_id=user.ID))

    elif callback.data.startswith('event_quiz_started'):
        num, user_answer = callback.data.replace('event_quiz_started?', '').split('&')
        num = int(num.replace('num=', ''))
        user_answer = user_answer.replace('answer=', '')
        question = await QuizDB.select(num=num)
        quiz_user = await QuizUserDB.select(user_id=user.ID)

        await callback.message.edit_text(text=f'{question.question}\n\n'
                                              f'*Правильный ответ:*     {question.answer}',
                                         reply_markup=None,
                                         parse_mode='Markdown')

        if user_answer[:10] == question.answer[:10]:
            await callback.message.answer_animation(animation=random.choice(true_stickers))
            await callback.message.answer(text=random.choice(true_answers))
            quiz_user.count_true_answers += 1

        else:
            await callback.message.answer_animation(animation=random.choice(wrong_stickers))
            await callback.message.answer(text=random.choice(wrong_answers))

        if num == 11:
            quiz_user.end_datetime = datetime.now()

        if question.desc:
            pause = len(question.desc) // 24
            await callback.message.answer(f'{question.desc}\n\n'
                                          f'Следующий вопрос через {pause} с')
            await asyncio.sleep(pause)

            try:
                await bot.edit_message_text(text=f'{question.desc}',
                                            chat_id=callback.message.chat.id,
                                            message_id=callback.message.message_id + 3,
                                            parse_mode='Markdown')
            except TelegramRetryAfter:
                pass

        if num < 11:
            question = await QuizDB.select(num=num + 1)
            await callback.message.answer(text=question.question,
                                          reply_markup=Keyboards.quiz_keyboard(question).as_markup(),
                                          parse_mode='Markdown')

        else:
            await callback.message.answer_animation(
                animation='CAACAgIAAxkBAAENuydnpTiNzWS2IdnMrurDoD893rBJZQACcAAD9wLIDyQpDCtech2jNgQ'
            )
            await callback.message.answer(text=f'Поздравляю! Ты завершаешь викторину, ответив верно на '
                                               f'{quiz_user.count_true_answers} из 11 вопросов! На прохождение ушло '
                                               f'{(quiz_user.end_datetime - quiz_user.start_datetime).total_seconds():.1f} c',
                                          parse_mode='Markdown')
            await callback.message.answer(text=event_schedule,
                                          reply_markup=Keyboards.main_keyboard(user).as_markup(),
                                          parse_mode='Markdown')

        await QuizUserDB.update(quiz_user)
