from io import BytesIO
from pprint import pprint

import aiohttp
import asyncio

from Config.Config import global_settings
from Scripts.Others import get_sex_of_person_by_name
from Server.Models import User


async def get_user_data_by_id(user: User, user_id: str) -> tuple | bool:
    async with aiohttp.ClientSession() as session:
        url = 'https://api.vk.com/method/users.get'
        data = {
            'user_ids': user_id,
            'access_token': global_settings.vk_main_token,
            'v': '5.199'
        }
        response = await session.get(url, params=data)
        data = await response.json()

        if data['response']:
            sex = get_sex_of_person_by_name(f"{data['response'][0]['first_name']} {data['response'][0]['last_name']}")
            sex = sex if sex != '0' else None

            return (data['response'][0]['id'],
                    data['response'][0]['first_name'],
                    data['response'][0]['last_name'],
                    sex)

        else:
            return False


async def get_vk_attachment(data: BytesIO, filename: str, type: str = 'doc') -> str:
    """
    Загружает байты на сервер вк
    :param type: Тип файла, "doc" или "photo"
    :param data: Файл в байтах
    :param filename: Имя файла
    :return: Строка формата {type}{owner_id}_{file_id}
    """
    params = {'access_token': global_settings.vk_main_token,
              'peer_id': '299407304',
              'v': '5.199'}

    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://api.vk.com/method/{type}s.getMessagesUploadServer',
                               params=params) as response:
            result = await response.json()
            server = result['response']['upload_url']

    async with aiohttp.ClientSession() as session:
        file = aiohttp.FormData()
        file.add_field(name='file',
                       value=data,
                       filename=filename)

        async with session.post(server, data=file) as response:
            result = await response.json()
            file = result['file'] if type == 'doc' else result['photo']

    params = {'access_token': global_settings.vk_main_token,
              'title': filename,
              'v': '5.199'}
    if type == 'doc':
        params['file'] = file
    else:
        params['photo'] = file
        params['server'] = result['server']
        params['hash'] = result['hash']

    async with aiohttp.ClientSession() as session:
        if type == 'doc':
            async with session.get(f'https://api.vk.com/method/docs.save',
                                   params=params) as response:
                result = await response.json()
        else:
            async with session.get(f'https://api.vk.com/method/photos.saveMessagesPhoto',
                                   params=params) as response:
                result = await response.json()

    if type == 'doc':
        vk_attach = (f'{result['response']['type']}{result['response']['doc']['owner_id']}_'
                     f'{result['response']['doc']['id']}')
    else:
        vk_attach = f'photo{result['response'][0]['owner_id']}_{result['response'][0]['id']}'

    return vk_attach


if __name__ == '__main__':
    asyncio.run(get_user_data_by_id('del_nick'))
