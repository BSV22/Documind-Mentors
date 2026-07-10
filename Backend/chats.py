import uuid
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException

from database import get_db_connection
from auth import get_current_user
from schemas import CreateChatRequest

router = APIRouter(prefix="/api/chats", tags=["chats"])

@router.get("")
def get_chats(current_user: dict = Depends(get_current_user)):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, title, created_at FROM chats WHERE user_id = %s ORDER BY created_at DESC", (current_user["id"],))
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("")
def create_chat(req: CreateChatRequest, current_user: dict = Depends(get_current_user)):
    chat_id = str(uuid.uuid4())
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO chats (id, title, user_id) VALUES (%s, %s, %s)", (chat_id, req.title, current_user["id"]))
            conn.commit()
        return {"id": chat_id, "title": req.title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{chat_id}")
def delete_chat(chat_id: str, current_user: dict = Depends(get_current_user)):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM chats WHERE id = %s AND user_id = %s", (chat_id, current_user["id"]))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Chat not found")
                # Cascade delete deletes messages from the database
                cursor.execute("DELETE FROM chats WHERE id = %s", (chat_id,))
            conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{chat_id}/messages")
def get_messages(chat_id: str, current_user: dict = Depends(get_current_user)):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id FROM chats WHERE id = %s AND user_id = %s", (chat_id, current_user["id"]))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Chat not found")
                    
                cursor.execute("SELECT id, from_user, text, timestamp FROM messages WHERE chat_id = %s ORDER BY timestamp ASC", (chat_id,))
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
