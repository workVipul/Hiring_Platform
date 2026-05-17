from sqlalchemy import create_engine, text

from app.core.config import settings


try:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("select 1")).scalar()
    print("CONNECTED SUCCESSFULLY")
except Exception as e:
    print(e)
