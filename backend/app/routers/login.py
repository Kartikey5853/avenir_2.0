from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging
from datetime import datetime, timedelta

from app.database import get_db
from app.models.user import User
from app.models.otp import OTP
from app.schemas.auth import LoginRequest, TokenResponse
from app.utils.security import verify_password
from app.utils.jwt import create_access_token , get_current_user
from app.utils.otp import generate_otp


router = APIRouter()


@router.post("/login")
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(
            User.email == payload.email.lower()
        ).first()

        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=400, detail="Invalid credentials")

        # If 2FA enabled → send OTP
        if user.two_factor_enabled:

            # 🔴 Delete any previous active OTPs
            db.query(OTP).filter(
                OTP.user_id == user.id,
                OTP.purpose == "login_2fa"
            ).delete()
            db.commit()

            otp_code = generate_otp()

            otp_entry = OTP(
                user_id=user.id,
                otp_code=otp_code,  # will hash later
                purpose="login_2fa",
                expires_at=datetime.utcnow() + timedelta(minutes=5),
                attempts=0,
                locked_until=None
            )

            db.add(otp_entry)
            db.commit()

            logging.info(f"2FA OTP for {user.email}: {otp_code}")

            return {
                "success": True,
                "message": "OTP required for login",
                "otp_required": True
            }

        # If 2FA disabled → issue JWT
        access_token = create_access_token({"sub": str(user.id)})

        return TokenResponse(
            access_token=access_token,
            user=user
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/verify-login-otp")
def verify_login_otp(email: str, otp_code: str, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(
            User.email == email.lower()
        ).first()

        if not user:
            raise HTTPException(status_code=400, detail="Invalid OTP")

        otp_entry = db.query(OTP).filter(
            OTP.user_id == user.id,
            OTP.purpose == "login_2fa"
        ).first()

        if not otp_entry:
            raise HTTPException(status_code=400, detail="Invalid OTP")

        # 🔐 Check if locked
        if otp_entry.locked_until and otp_entry.locked_until > datetime.utcnow():
            raise HTTPException(
                status_code=403,
                detail="Too many failed attempts. Try again later."
            )

        # 🔐 Check expiry
        if otp_entry.expires_at < datetime.utcnow():
            db.delete(otp_entry)
            db.commit()
            raise HTTPException(status_code=400, detail="OTP expired")

        # 🔐 Verify OTP
        if otp_entry.otp_code != otp_code:

            otp_entry.attempts += 1

            # Lock if max attempts reached
            if otp_entry.attempts >= otp_entry.max_attempts:
                otp_entry.locked_until = datetime.utcnow() + timedelta(minutes=10)

            db.commit()

            raise HTTPException(status_code=400, detail="Invalid OTP")

        # ✅ Successful verification
        db.delete(otp_entry)
        db.commit()

        access_token = create_access_token({"sub": str(user.id)})

        return TokenResponse(
            access_token=access_token,
            user=user
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"OTP verification error: {str(e)}")
        raise HTTPException(status_code=500, detail="OTP verification failed")


#2FA enable route 

@router.post("/enable-2fa")
def enable_2fa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.email_verified:
        raise HTTPException(status_code=400, detail="Verify email first")

    current_user.two_factor_enabled = True
    db.commit()

    return {"success": True, "message": "2FA enabled"}