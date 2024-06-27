import os

from dotenv import load_dotenv
from pocketbase import PocketBase

load_dotenv()

PB = PocketBase("http://pocketbase:8090")


async def pb_login():
    await PB.admins.auth.with_password(os.getenv("PB_EMAIL"), os.getenv("PB_PASSWORD"))
