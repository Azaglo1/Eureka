#!/usr/bin/env python3
"""
Migration script to add the 'body' column to the messages table
"""
import sqlite3
import os

DATABASE = os.path.join(os.path.dirname(__file__), "school.db")

def migrate():
    db = sqlite3.connect(DATABASE)
    cur = db.cursor()
    
    try:
        # Check if body column exists
        cur.execute("PRAGMA table_info(messages)")
        columns = {row[1] for row in cur.fetchall()}
        
        if 'body' not in columns:
            print("Adding 'body' column to messages table...")
            cur.execute("ALTER TABLE messages ADD COLUMN body TEXT")
            db.commit()
            print("✓ Successfully added 'body' column to messages table")
        else:
            print("✓ 'body' column already exists in messages table")
    except sqlite3.OperationalError as e:
        print(f"✗ Error during migration: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
