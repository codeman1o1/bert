import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

db = psycopg.connect(os.getenv("DATABASE_URL"))
