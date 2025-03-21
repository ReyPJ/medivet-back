from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.base import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.crud.crud_user import (
    get_users,
    create_user,
    get_user,
    update_user,
    get_users_by_role,
)
from app.api.deps import get_current_active_user, get_current_user_with_role

router = APIRouter()


@router.get("/", response_model=List[UserRead])
def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_with_role(["admin"])),
):
    users = get_users(db, skip=skip, limit=limit)
    return users


# List users with the role "asistant" without the need of being an admin
# Just being authenticated
@router.get("/assistants", response_model=List[UserRead])
def read_assistants(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    users = get_users_by_role(db, role="assistant", skip=skip, limit=limit)
    return users


@router.post("/", response_model=UserRead)
def create_new_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_with_role(["admin"])),
):
    return create_user(db=db, user=user)


@router.get("/me", response_model=UserRead)
def read_user_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.get("/{user_id}", response_model=UserRead)
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Regular users can only see their own profile
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    db_user = get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.put("/{user_id}", response_model=UserRead)
def update_user_info(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Regular users can only update their own profile
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # Only admins can change roles
    if (
        "role" in user_data.model_dump(exclude_unset=True)
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can change roles",
        )

    return update_user(db, user_id=user_id, user=user_data)
