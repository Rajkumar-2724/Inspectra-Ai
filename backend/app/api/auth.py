from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.security import create_access_token, hash_password, verify_password
from app.database.session import get_db
from app.models import Role, User
from app.schemas.schemas import (ChangePasswordIn, LoginIn, RegisterIn, TokenOut, UserAdminIn, UserAdminPatch, UserOut)

router = APIRouter(prefix="/api", tags=["auth"])


def _exists(db: Session, email: str, username: str) -> bool:
    return db.execute(select(User).where(or_(User.email == email.lower(), User.username == username))).first() is not None


@router.post("/auth/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """Public self-registration always creates a Quality Inspector. Admins assign other roles."""
    if _exists(db, body.email, body.username):
        raise HTTPException(409, "Email or username already registered")
    u = User(email=body.email.lower(), username=body.username, full_name=body.full_name,
             hashed_password=hash_password(body.password), role=Role.inspector)
    db.add(u)
    db.commit()
    return u


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.execute(select(User).where(or_(User.username == body.username, User.email == body.username.lower()))).scalar_one_or_none()
    if u is None or not u.is_active or not verify_password(body.password, u.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password")
    return TokenOut(access_token=create_access_token(str(u.id), u.role.value), user=UserOut.model_validate(u))


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/auth/change-password", status_code=204)
def change_password(body: ChangePasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    user.hashed_password = hash_password(body.new_password)
    db.commit()


@router.get("/users", response_model=list[UserOut])
def list_users(_: User = Depends(require_roles()), db: Session = Depends(get_db)):
    return db.execute(select(User).order_by(User.id)).scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserAdminIn, _: User = Depends(require_roles()), db: Session = Depends(get_db)):
    if _exists(db, body.email, body.username):
        raise HTTPException(409, "Email or username already registered")
    u = User(email=body.email.lower(), username=body.username, full_name=body.full_name,
             hashed_password=hash_password(body.password), role=body.role)
    db.add(u)
    db.commit()
    return u


@router.patch("/users/{user_id}", response_model=UserOut)
def patch_user(user_id: int, body: UserAdminPatch, admin: User = Depends(require_roles()), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == admin.id and (body.is_active is False or (body.role and body.role != Role.admin)):
        raise HTTPException(400, "Admins cannot demote or disable themselves")
    if body.role is not None:
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    db.commit()
    return u
