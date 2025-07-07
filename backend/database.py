import sqlite3
import os
import json
from dotenv import load_dotenv

load_dotenv()
db_path = os.getenv("DB_PATH")

class DatabaseSingleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseSingleton, cls).__new__(cls)
            cls._instance.conn = sqlite3.connect(db_path, check_same_thread=False)
            cls._instance.conn.execute("PRAGMA foreign_keys = ON;")  
            cls._instance.cursor = cls._instance.conn.cursor()
        return cls._instance

    def execute(self, query, params=()):
        self.cursor.execute(query, params)
        self.conn.commit()

    def fetchall(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def fetchone(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchone()

    def close(self):
        self.conn.close()
        DatabaseSingleton._instance = None

# ---------------------------- INIT ----------------------------

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
    db.execute("""
        CREATE TABLE IF NOT EXISTS chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            usermessage TEXT NOT NULL,
            botmessage TEXT NOT NULL,
            context TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(chat_id) REFERENCES chat(id) ON DELETE CASCADE
        );
    """)

# ---------------------------- PDF ----------------------------

def insert_pdf_file(filename, filepath, description):
    db = DatabaseSingleton()
    db.execute("INSERT INTO pdf_files (filename, filepath, description) VALUES (?, ?, ?)", (filename, filepath, description))

def delete_pdf_file(filename):
    db = DatabaseSingleton()
    db.execute("DELETE FROM pdf_files WHERE filename = ?", (filename, ))

def get_file(filename):
    db = DatabaseSingleton()
    result = db.fetchall("SELECT filename, filepath, description FROM pdf_files WHERE filename = ?", (filename, ))
    filename, filepath, index_id = result[0]
    return filename, filepath, index_id

def get_all_files():
    db = DatabaseSingleton()
    rows = db.fetchall("SELECT * FROM pdf_files")
    columns = ['id', 'filename', 'filepath', 'description','uploaded_at']
    return [dict(zip(columns, row)) for row in rows]

# ---------------------------- Chat ----------------------------

def insert_chat(name):
    db = DatabaseSingleton()
    db.execute("INSERT INTO chat (name) VALUES (?)", (name,))
    return db.cursor.lastrowid

def get_all_chats():
    db = DatabaseSingleton()
    rows = db.fetchall("SELECT * FROM chat")
    columns = ['id', 'name', 'created_at']
    return [dict(zip(columns, row)) for row in rows]

def update_chat_name(chat_id, new_name):
    db = DatabaseSingleton()
    db.execute("UPDATE chat SET name = ? WHERE id = ?", (new_name, chat_id))
    return db.fetchone("SELECT name FROM chat WHERE id = ?", (chat_id,))[0]

def delete_chat(chat_id):
    db = DatabaseSingleton()
    db.execute("DELETE FROM chat WHERE id = ?", (chat_id,))

# ---------------------------- Chat Messages ----------------------------

def insert_chat_message(chat_id, usermessage, botmessage, context):
    db = DatabaseSingleton()
    if isinstance(context, list):
        context = json.dumps(context)
    db.execute("""
        INSERT INTO chat_messages (chat_id, usermessage, botmessage, context)
        VALUES (?, ?, ?, ?)
    """, (chat_id, usermessage, botmessage, context))
    return db.cursor.lastrowid

def get_chat_messages(chat_id):
    db = DatabaseSingleton()
    rows = db.fetchall("SELECT id, chat_id, usermessage, botmessage FROM chat_messages WHERE chat_id = ?", (chat_id,))
    return [{'id':r[0], 'chat_id':r[1], 'usermessage': r[2], 'botmessage': r[3]} for r in rows]

def get_all_chat_messages():
    db = DatabaseSingleton()
    rows = db.fetchall("SELECT id, chat_id, usermessage, botmessage, context FROM chat_messages")
    messages = []
    for r in rows:
        try:
            context = json.loads(r[4])
        except (json.JSONDecodeError, TypeError):
            context = []  
        messages.append({
            'id': r[0],
            'chat_id': r[1],
            'usermessage': r[2],
            'botmessage': r[3],
            'context': context
        })
    return messages

def delete_messages_after(message_id, chat_id):
    db = DatabaseSingleton()
    result = db.fetchone(
        "SELECT created_at FROM chat_messages WHERE id = ? AND chat_id = ?",
        (message_id, chat_id)
    )
    if not result:
        raise ValueError("Message not found for deletion.")
    created_at = result[0]
    db.execute(
        "DELETE FROM chat_messages WHERE chat_id = ? AND created_at >= ?",
        (chat_id, created_at)
    )


