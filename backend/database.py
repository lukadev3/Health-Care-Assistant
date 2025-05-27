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
            description TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

def insert_pdf_file(filename, filepath, description):
    db = DatabaseSingleton()
    db.execute("INSERT INTO pdf_files (filename, filepath, description) VALUES (?, ?, ?)", (filename, filepath, description))

def delete_pdf_file(filename):
    db = DatabaseSingleton()
    db.execute("DELETE FROM pdf_files WHERE filename = ?", (filename, ))

def get_file(filename):
    db = DatabaseSingleton()
    result = db.fetchall("SELECT filename, filepath FROM pdf_files WHERE filename = ?", (filename, ))
    filename, filepath, index_id = result[0]
    return filename, filepath, index_id

def get_all_files():
    db = DatabaseSingleton()
    rows = db.fetchall("SELECT * FROM pdf_files")
    columns = ['id', 'filename', 'filepath', 'description','uploaded_at']
    return [dict(zip(columns, row)) for row in rows]
