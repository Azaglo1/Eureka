#!/usr/bin/env python3
"""
Manually fix the messages table schema
"""
import sqlite3
import os

DATABASE = os.path.join(os.path.dirname(__file__), "school.db")

def fix_messages():
    db = sqlite3.connect(DATABASE)
    cur = db.cursor()
    
    try:
        # Check current schema
        cur.execute("PRAGMA table_info(messages)")
        columns = {row[1] for row in cur.fetchall()}
        print(f"Current columns: {columns}")
        
        # If we have both content and body, or just content, we need to fix it
        if 'content' in columns:
            print("\nRecreating messages table without 'content' column...")
            
            # Create new table with correct schema
            cur.execute("""
                CREATE TABLE messages_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER NOT NULL,
                    recipient_id INTEGER NOT NULL,
                    school_id INTEGER NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    read_at TEXT,
                    FOREIGN KEY(sender_id) REFERENCES users(id),
                    FOREIGN KEY(recipient_id) REFERENCES users(id),
                    FOREIGN KEY(school_id) REFERENCES schools(id)
                )
            """)
            
            # Copy data
            if 'body' in columns:
                # If body already exists, copy body from body
                cur.execute("INSERT INTO messages_new SELECT id, sender_id, recipient_id, school_id, subject, body, created_at, read_at FROM messages WHERE body IS NOT NULL")
                print("Copied data from existing 'body' column")
            else:
                # Copy from content (rename it to body)
                cur.execute("INSERT INTO messages_new SELECT id, sender_id, recipient_id, school_id, subject, content, created_at, read_at FROM messages WHERE content IS NOT NULL")
                print("Copied data from 'content' column (renamed to 'body')")
            
            # Drop old and rename new
            cur.execute("DROP TABLE messages")
            cur.execute("ALTER TABLE messages_new RENAME TO messages")
            db.commit()
            print("✓ Successfully fixed messages table!")
        else:
            print("✓ Messages table is already correct")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_messages()
