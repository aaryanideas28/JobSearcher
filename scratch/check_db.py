from sqlalchemy import inspect
from database.connection import engine, init_db

def main():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("Existing tables in database:", tables)
    if not tables:
        print("No tables found. Initializing database schema...")
        init_db()
        tables_after = inspector.get_table_names()
        print("Tables after initialization:", tables_after)
    else:
        print("Tables already exist.")

if __name__ == "__main__":
    main()
