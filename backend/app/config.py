import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://exp:exp@localhost:5434/exp"
)
PORT = int(os.getenv("PORT", "8002"))
