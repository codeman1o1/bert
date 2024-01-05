import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

DB = psycopg.connect(os.getenv("DATABASE_URL"))
