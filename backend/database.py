import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

db_path = os.getenv("DB_PATH")

class DatabaseSingleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseSingleton, cls).__new__(cls)
            cls._instance.conn = sqlite3.connect(db_path, check_same_thread=False)
            cls._instance.cursor = cls._instance.conn.cursor()
        return cls._instance

    def execute(self, query, params=()):
        self.cursor.execute(query, params)
        self.conn.commit()

    def fetchall(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()
        DatabaseSingleton._instance = None

def init_db():
    db = DatabaseSingleton()
    db.execute("""
        CREATE TABLE IF NOT EXISTS pdf_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

def insert_pdf_file(filename, filepath):
    db = DatabaseSingleton()
    db.execute("INSERT INTO pdf_files (filename, filepath) VALUES (?, ?)", (filename, filepath))

def delete_pdf_file(filename):
    db = DatabaseSingleton()
    db.execute("DELETE FROM pdf_files WHERE filename = ?", (filename,))

def get_all_files():
    db = DatabaseSingleton()
    return db.fetchall("SELECT filename, filepath FROM pdf_files")
