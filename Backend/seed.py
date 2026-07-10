import sys
import os
import uuid

# Add current folder to sys.path so we can import from database and auth
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
from auth import hash_password

def seed_db():
    print("Starting database seeding...")
    
    # 1. Seed Demo User
    demo_email = "demo@example.com"
    demo_name = "Demo User"
    demo_password = "Password123"
    hashed = hash_password(demo_password)
    
    user_id = None
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Check if user already exists
                cursor.execute("SELECT id FROM users WHERE email = %s", (demo_email,))
                user_row = cursor.fetchone()
                
                if user_row:
                    user_id = user_row[0]
                    print(f"User {demo_email} already exists (ID: {user_id}). Skipping user creation...")
                    
                    # Update password and set verified to True just in case
                    cursor.execute(
                        "UPDATE users SET name = %s, password_hash = %s, is_verified = TRUE WHERE id = %s",
                        (demo_name, hashed, user_id)
                    )
                    print(f"Updated user password and verification status.")
                else:
                    # Create new verified user
                    cursor.execute(
                        "INSERT INTO users (name, email, password_hash, is_verified) VALUES (%s, %s, %s, TRUE) RETURNING id",
                        (demo_name, demo_email, hashed)
                    )
                    user_id = cursor.fetchone()[0]
                    print(f"Created verified demo user {demo_email} (ID: {user_id}).")
                
                # 2. Seed default chats and messages
                # Check if chats already exist for this user
                cursor.execute("SELECT id FROM chats WHERE user_id = %s", (user_id,))
                chat_row = cursor.fetchone()
                
                if chat_row:
                    print("Chats already exist for this user. Skipping chat history seeding...")
                else:
                    # Seed Chat 1
                    chat1_id = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO chats (id, title, user_id) VALUES (%s, %s, %s)",
                        (chat1_id, "Introduction to RAG", user_id)
                    )
                    
                    # Chat 1 Messages
                    msg1_id = str(uuid.uuid4())
                    msg2_id = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO messages (id, chat_id, from_user, text) VALUES (%s, %s, TRUE, %s)",
                        (msg1_id, chat1_id, "How does RAG work?")
                    )
                    cursor.execute(
                        "INSERT INTO messages (id, chat_id, from_user, text) VALUES (%s, %s, FALSE, %s)",
                        (msg2_id, chat1_id, "Retrieval-Augmented Generation (RAG) is a technique that enhances LLMs by retrieving relevant document passages first, and passing them as context with your query. This keeps answers grounded in your custom data.")
                    )
                    
                    # Seed Chat 2
                    chat2_id = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO chats (id, title, user_id) VALUES (%s, %s, %s)",
                        (chat2_id, "Getting Started with Documind", user_id)
                    )
                    
                    # Chat 2 Messages
                    msg3_id = str(uuid.uuid4())
                    msg4_id = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO messages (id, chat_id, from_user, text) VALUES (%s, %s, TRUE, %s)",
                        (msg3_id, chat2_id, "Hello!")
                    )
                    cursor.execute(
                        "INSERT INTO messages (id, chat_id, from_user, text) VALUES (%s, %s, FALSE, %s)",
                        (msg4_id, chat2_id, "Welcome to Documind! You can upload PDF documents in the left sidebar and start chatting with them in real-time. Let me know if you have any questions!")
                    )
                    
                    print("Seeded default chat sessions and message histories successfully.")
                    
            conn.commit()
            print("Database seeding completed successfully!")
            print(f"\nDefault credentials:\nEmail: {demo_email}\nPassword: {demo_password}\n")
    except Exception as e:
        print("Database seeding failed:", e)

if __name__ == "__main__":
    seed_db()
