from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv, dotenv_values
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

load_dotenv(find_dotenv("dfg.env"))


@dataclass
class GlobalSettings:
    config = dotenv_values()

    host: str = config['host']
    user: str = config['user']
    password: str = config['password']
    db_name: str = config['db_name']
    port: int = config['port']

    vk_ss_ff_token: str = config['vk_ss_ff_token']
    vk_main_token: str = config['vk_main_token']

    main_token: str = config['tg_main_token']
    test_bot_token: str = config['tg_test_token']
    owner_id: str = config['owner_id']

    ssh_host: str = config['ssh_host']
    ssh_username: str = config['ssh_username']
    ssh_password: str = config['ssh_password']
    ssh_port: int = config['ssh_port']

    admins = tuple(map(int, config['tg_admins'].split()))

    def __init__(self):
        self.engine = create_async_engine(url=self.DATABASE_URL_asyncpg,
                                          echo=False,
                                          pool_size=15,
                                          max_overflow=5,
                                          pool_recycle=3600,
                                          pool_timeout=10)
        self.session_factory = async_sessionmaker(self.engine)
        self.MAIN_BOT = False

    @property
    def DATABASE_URL_asyncpg(self):
        # postgresql+asyncpg://postgres:postgres@localhost:5432/sa
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}"


global_settings = GlobalSettings()