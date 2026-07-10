import datetime
import os
import bcrypt
import jwt
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from google.oauth2 import id_token
from google.auth.transport import requests

from config import JWT_SECRET, ALGORITHM
from database import get_db_connection
from schemas import SignupRequest, SigninRequest, GoogleAuthRequest, VerifyOtpRequest, ResendOtpRequest, ForgotPasswordRequest, ResetPasswordRequest
from email_utils import send_otp_email


router = APIRouter(prefix="/api/auth", tags=["auth"])

# JWT Helpers
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

# Auth dependency
def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    
    # Verify user exists in the database
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name, email FROM users WHERE id = %s", (payload.get("id"),))
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User session is invalid. Please sign in again.",
                    )
                return {"id": row[0], "name": row[1], "email": row[2]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database user validation failed: {str(e)}"
        )

# Password utils
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Endpoints
@router.post("/signup")
def signup(req: SignupRequest, response: Response):
    import random
    hashed = hash_password(req.password)
    otp_code = f"{random.randint(100000, 999999)}"
    otp_expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Check if email is already registered
                cursor.execute("SELECT id, is_verified FROM users WHERE email = %s", (req.email,))
                existing_user = cursor.fetchone()
                
                if existing_user:
                    if existing_user["is_verified"]:
                        raise HTTPException(status_code=400, detail="Email already registered")
                    else:
                        # User exists but is unverified. Overwrite details and send new OTP.
                        cursor.execute(
                            "UPDATE users SET name = %s, password_hash = %s, otp_code = %s, otp_expires_at = %s WHERE id = %s RETURNING id",
                            (req.name, hashed, otp_code, otp_expires_at, existing_user["id"])
                        )
                        user_id = cursor.fetchone()[0]
                else:
                    # New user signup
                    cursor.execute(
                        "INSERT INTO users (name, email, password_hash, is_verified, otp_code, otp_expires_at) VALUES (%s, %s, %s, FALSE, %s, %s) RETURNING id",
                        (req.name, req.email, hashed, otp_code, otp_expires_at)
                    )
                    user_id = cursor.fetchone()[0]
            conn.commit()
    except HTTPException as he:
        raise he
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=400, detail="Email already registered")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # Send verification email (falls back to console printing if SMTP is not configured)
    send_otp_email(req.email, otp_code)
    
    return {"status": "verification_required", "email": req.email}

@router.post("/verify-otp")
def verify_otp(req: VerifyOtpRequest, response: Response):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute(
                    "SELECT id, name, email, otp_code, otp_expires_at FROM users WHERE email = %s",
                    (req.email,)
                )
                user = cursor.fetchone()
                
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")
                
                if not user["otp_code"] or not user["otp_expires_at"]:
                    raise HTTPException(status_code=400, detail="No OTP code requested for this email")
                
                if user["otp_code"] != req.otp:
                    raise HTTPException(status_code=400, detail="Invalid verification code")
                
                # Check expiration (offset-naive vs offset-aware: utcnow is naive)
                now = datetime.datetime.utcnow()
                if user["otp_expires_at"] < now:
                    raise HTTPException(status_code=400, detail="Verification code has expired")
                
                # Update user as verified
                cursor.execute(
                    "UPDATE users SET is_verified = TRUE, otp_code = NULL, otp_expires_at = NULL WHERE id = %s",
                    (user["id"],)
                )
                conn.commit()
                
                user_data = {"id": user["id"], "email": user["email"], "name": user["name"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
    token = create_access_token(user_data)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 3600,
        samesite="lax",
        secure=False,
        path="/"
    )
    return {"user": user_data}

@router.post("/resend-otp")
def resend_otp(req: ResendOtpRequest):
    import random
    otp_code = f"{random.randint(100000, 999999)}"
    otp_expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, is_verified FROM users WHERE email = %s", (req.email,))
                user = cursor.fetchone()
                
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")
                
                if user["is_verified"]:
                    return {"status": "already_verified", "message": "Email is already verified"}
                
                cursor.execute(
                    "UPDATE users SET otp_code = %s, otp_expires_at = %s WHERE id = %s",
                    (otp_code, otp_expires_at, user["id"])
                )
                conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
    # Send verification email (falls back to console printing if SMTP is not configured)
    send_otp_email(req.email, otp_code)
    
    return {"status": "success", "message": "Verification code resent successfully"}

@router.post("/signin")
def signin(req: SigninRequest, response: Response):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, name, email, password_hash, is_verified FROM users WHERE email = %s", (req.email,))
                user = cursor.fetchone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
    if not user or not user["password_hash"]:
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    if not user["is_verified"]:
        raise HTTPException(status_code=403, detail="Email verification pending")
        
    user_data = {"id": user["id"], "email": user["email"], "name": user["name"]}
    token = create_access_token(user_data)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 3600,
        samesite="lax",
        secure=False,
        path="/"
    )
    return {"user": user_data}

@router.post("/google")
def google_auth(req: GoogleAuthRequest, response: Response):
    try:
        client_id = os.getenv("GOOGLE_CLIENT_ID", "821514705181-4j2t6hghcn168s32hoinvuo8vf1kl84i.apps.googleusercontent.com")
        idinfo = id_token.verify_oauth2_token(req.token, requests.Request(), client_id)
        
        email = idinfo['email']
        name = idinfo.get('name', '')
        sub = idinfo['sub']
    except Exception as e:
        print("Google token verification failed:", e)
        raise HTTPException(status_code=401, detail=f"Google authentication failed: {str(e)}")
        
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, name, email FROM users WHERE google_sub = %s OR email = %s", (sub, email))
                user = cursor.fetchone()
                
                if not user:
                    cursor.execute(
                        "INSERT INTO users (name, email, google_sub, is_verified) VALUES (%s, %s, %s, TRUE) RETURNING id",
                        (name, email, sub)
                    )
                    user_id = cursor.fetchone()[0]
                    user_name = name
                    conn.commit()
                else:
                    user_id = user["id"]
                    user_name = user["name"]
                    cursor.execute("UPDATE users SET google_sub = %s, is_verified = TRUE WHERE id = %s", (sub, user_id))
                    conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
            
    user_data = {"id": user_id, "email": email, "name": user_name}
    token = create_access_token(user_data)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 3600,
        samesite="lax",
        secure=False,
        path="/"
    )
    return {"user": user_data}

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}

@router.post("/signout")
def signout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    return {"status": "success"}

@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    import random
    otp_code = f"{random.randint(100000, 999999)}"
    otp_expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id FROM users WHERE email = %s", (req.email,))
                user = cursor.fetchone()
                
                if not user:
                    raise HTTPException(status_code=404, detail="Email address not found")
                
                cursor.execute(
                    "UPDATE users SET otp_code = %s, otp_expires_at = %s WHERE id = %s",
                    (otp_code, otp_expires_at, user["id"])
                )
                conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
    # Send verification email
    send_otp_email(req.email, otp_code)
    
    return {"status": "success", "message": "Password reset code sent successfully"}

@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute(
                    "SELECT id, otp_code, otp_expires_at FROM users WHERE email = %s",
                    (req.email,)
                )
                user = cursor.fetchone()
                
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")
                
                if not user["otp_code"] or not user["otp_expires_at"]:
                    raise HTTPException(status_code=400, detail="No reset code requested for this email")
                
                if user["otp_code"] != req.otp:
                    raise HTTPException(status_code=400, detail="Invalid verification code")
                
                now = datetime.datetime.utcnow()
                if user["otp_expires_at"] < now:
                    raise HTTPException(status_code=400, detail="Verification code has expired")
                
                hashed = hash_password(req.new_password)
                cursor.execute(
                    "UPDATE users SET password_hash = %s, otp_code = NULL, otp_expires_at = NULL WHERE id = %s",
                    (hashed, user["id"])
                )
                conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
    return {"status": "success", "message": "Password reset successfully. You can now sign in."}

