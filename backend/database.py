import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

db_path = os.getenv("DB_PATH")

def init_db():
    if not os.path.exists(db_path):  
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pdf_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()

def insert_pdf_file(filename, filepath):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pdf_files (filename, filepath) VALUES (?, ?)", (filename, filepath))
    conn.commit()
    conn.close()

def get_all_files():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT filename, filepath FROM pdf_files")
    files = cursor.fetchall()
    conn.close()
    return files
