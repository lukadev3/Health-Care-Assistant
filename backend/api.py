import os
import sqlite3
from flask import Flask, request, jsonify
from rag import handle_upload, query_tools, load_tools
from database import init_db, insert_pdf_file, get_all_files
from dotenv import load_dotenv

load_dotenv()

init_db()  

db_path = os.getenv("DB_PATH")
folder_path = os.getenv("FOLDER_PATH")
app = Flask(__name__)

tools = []

files = get_all_files()
for filename, filepath in files:
    vector_query_tool, summary_tool = load_tools(filepath, filename)
    tools.append(vector_query_tool)
    tools.append(summary_tool)


@app.route("/", methods=["GET"])
def home():
    return "Hello, World!"

@app.route("/upload", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    filename = file.filename 

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    filepath = os.path.join(folder_path, filename)
    file.save(filepath)

    filename = os.path.splitext(filename)[0]
    insert_pdf_file(filename, filepath)

    vector_query_tool, summary_tool = handle_upload(filepath, filename)
    tools.append(vector_query_tool)
    tools.append(summary_tool)

    return jsonify({"message": f"PDF {filename} uploaded successfully!"})

@app.route("/query", methods=["GET"])
def query_pdf():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Query is required"}), 400
    result = query_tools(query, tools)
    return jsonify({"result" : result})

if __name__ == "__main__":
    app.run(debug=True)