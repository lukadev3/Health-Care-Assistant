import os
import shutil
import asyncio
from quart import Quart, request, jsonify, Response, send_file
from quart_cors import cors
from rag import handle_upload, query_document, load_query_tool, delete_document
from database import init_db, insert_pdf_file, get_file, delete_pdf_file, get_all_files, insert_chat_message, get_chat_messages, insert_chat, get_all_chats, delete_chat
from dotenv import load_dotenv

import nest_asyncio
nest_asyncio.apply()

load_dotenv()
init_db()  

folder_path = os.getenv("FOLDER_PATH")
storage_context_path = os.getenv("STORAGE_CONTEXT_PATH")
app = Quart(__name__)
app = cors(app, allow_origin=["http://localhost:5173", "http://127.0.0.1:5173"])

tools = []
all_files = []
all_chats = []

async def load_tools_in_background():
    global tools, all_files
    all_files = get_all_files()
    all_chats = get_all_chats()

    for file in all_files:
        filename = os.path.splitext(file["filename"])[0]
        description = file['description']
        try:
            tool = await asyncio.to_thread(load_query_tool, filename, description)
            tools.append(tool)
            print(f"Tool loaded for {filename}")
        except Exception as e:
            print(f"Failed to load tool for {filename}: {e}")


# ---------------------------- File Routes ----------------------------

@app.before_serving
async def startup():
    asyncio.create_task(load_tools_in_background())

@app.route("/files/<filename>", methods=["GET"])
async def open_file(filename):
    file_record = get_file(filename)
    if not file_record:
        return jsonify({"error": "File not found"}), 404
    
    _, filepath, _ = file_record
    return await send_file(filepath, as_attachment=False)

@app.route("/files", methods=["GET"])
async def list_files():
    global all_files
    return jsonify({"files": all_files})

@app.route("/upload", methods=["POST"])
async def upload_pdf():
    global tools, all_files
    form = await request.files  

    if "file" not in form:
        return jsonify({"error": "No file provided"}), 400
    
    file = form["file"]
    filename = file.filename 

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    filepath = os.path.join(folder_path, filename)
    await file.save(filepath)

    tool, description = handle_upload(filepath, os.path.splitext(filename)[0])
    tools.append(tool)
    insert_pdf_file(filename, filepath, description)
    all_files = get_all_files()

    return jsonify({"message": f"PDF {filename} uploaded successfully!"})

@app.route("/delete", methods=["DELETE"])
async def delete_pdf(): 
    global tools, all_files
    form = await request.files

    if "file" not in form:
        return jsonify({"error": "No file provided"}), 400
    
    file = form["file"]
    filename = file.filename

    _, file_path, _ = get_file(filename)
    os.remove(file_path)
    file_storage_context_path = os.path.join(storage_context_path, os.path.splitext(filename)[0])
    if os.path.isdir(file_storage_context_path):
        shutil.rmtree(file_storage_context_path, ignore_errors=True)

    delete_pdf_file(filename)
    delete_document(os.path.splitext(filename)[0])
    tools = [tool for tool in tools if tool.metadata.name != os.path.splitext(filename)[0]]
    all_files = get_all_files()

    return jsonify({"message": f"PDF {filename} deleted successfully!"})

@app.route("/query", methods=["GET"])
async def query_pdf():
    global tools, all
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Query is required"}), 400
    id = request.args.get("id")
    if not id:
        return jsonify({"error": "Chat id is required"}), 400

    if len(tools) < len(all_files):
        return jsonify({
            "status": "loading",
            "message": "Tools are still loading. Please try again shortly."
        }), 503
    
    chat_history = []
    for chat in all_chats:
        if(chat['id'] == id):
            conversation = (chat['botmessage'], chat['usermessage'])
            chat_history.append(conversation)
    try:
        response = query_document(query, tools, chat_history)
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": f"An error occurred while generating a response: {str(e)}"}), 500
    
# ---------------------------- Chat Routes ----------------------------

@app.route("/chats", methods=["GET"])
async def list_chats():
    chats = get_all_chats()
    return jsonify({"chats": chats})

@app.route("/chats", methods=["POST"])
async def create_chat():
    data = await request.get_json()
    name = data.get("name", f"Chat {len(get_all_chats()) + 1}")  # Default name if not provided
    
    chat_id = insert_chat(name)
    return jsonify({
        "message": "Chat created successfully", 
        "chat_id": chat_id,
        "chat_name": name
    })

@app.route("/chats/<int:chat_id>", methods=["DELETE"])
async def remove_chat(chat_id):
    delete_chat(chat_id)
    return jsonify({"message": f"Chat {chat_id} and its messages deleted successfully"})

@app.route("/chats/<int:chat_id>/messages", methods=["GET"])
async def get_messages(chat_id):
    messages = get_chat_messages(chat_id)
    return jsonify({"messages": messages})

@app.route("/chats/<int:chat_id>/messages", methods=["POST"])
async def add_message(chat_id):
    data = await request.get_json()
    usermessage = data.get("usermessage")
    botmessage = data.get("botmessage")

    if not usermessage or not botmessage:
        return jsonify({"error": "Both usermessage and botmessage are required"}), 400

    insert_chat_message(chat_id, usermessage, botmessage)
    return jsonify({"message": "Message added successfully"})

