from app.database import engine, Base
from app.models import db  # noqa: F401 - imports models so they register

def init():
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

if __name__ == "__main__":
    init()
