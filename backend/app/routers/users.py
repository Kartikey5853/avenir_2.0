from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging

from app.database import get_db
from app.models.user import User
from app.schemas.auth import RegisterRequest, UserResponse
from app.utils.security import hash_password

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Create user
        new_user = User(
            name=payload.name.strip(),
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
            email_verified=False,
            two_factor_enabled=False
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logging.info(f"User registered: {new_user.email}")

        return new_user

    except HTTPException:
        raise

    except IntegrityError as e:
        db.rollback()
        logging.warning(f"Integrity error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed due to data conflict"
        )

    except Exception as e:
        db.rollback()
        logging.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong during registration"
        )