from sqlalchemy.orm import Session

from app.db.base import Base, engine, SessionLocal
from app.models import user
from app.crud.crud_user import create_user
from app.schemas.user import UserCreate


def init_db(db: Session) -> None:
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    if not db.query(user.User).filter(user.User.role == "admin").first():
        admin_user = UserCreate(
            username="admin",
            email="admin@example.com",
            password="admin123",
            full_name="Admin User",
            role="admin",
            phone="+50660793603",
        )
        create_user(db=db, user=admin_user)

    db.close()
