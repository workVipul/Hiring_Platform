from sqlalchemy import create_engine

DATABASE_URL = "postgresql://postgres:@127.0.0.1:5432/jdforge"

try:
    engine = create_engine(DATABASE_URL)

    conn = engine.connect()

    print("CONNECTED SUCCESSFULLY")

    conn.close()

except Exception as e:
    print(e)