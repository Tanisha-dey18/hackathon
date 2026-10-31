from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..infra import rate_limit
from ..models import User
from ..security import create_token, get_current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "customer_id": u.customer_id}


@router.post("/login", dependencies=[Depends(rate_limit(10, "login"))])
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.execute(select(User).where(User.email == body.email.lower())).scalar()
    if not u or not u.is_active or not verify_password(body.password, u.password_hash):
        audit.record(db, "LOGIN_FAILED", "user", body.email.lower(), {}, actor_label="anonymous")
        db.commit()
        raise HTTPException(401, "Invalid email or password")
    audit.record(db, "LOGIN", "user", str(u.id), {"role": u.role}, actor=u)
    db.commit()
    return {"access_token": create_token(u), "token_type": "bearer", "user": user_out(u)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)
