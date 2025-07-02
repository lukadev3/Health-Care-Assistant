import os
import shutil
import asyncio
from quart import Quart, request, jsonify, Response, send_file
from quart_cors import cors
from rag import handle_upload, query_document, load_query_tool, delete_document
from database import (init_db, insert_pdf_file, delete_pdf_file, get_all_files, 
                      insert_chat_message, get_all_chat_messages, insert_chat, get_all_chats, delete_chat, update_chat_name, delete_messages_after)
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
all_chats_messages = []

async def load_tools_in_background():
    global tools, all_files, all_chats_messages, all_chats
    all_files = get_all_files()
    all_chats = get_all_chats()
    all_chats_messages = get_all_chat_messages()

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
    global all_files
    for file in all_files:
        if(file['filename'] == filename):
            file_record = file

    if not file_record:
        return jsonify({"error": "File not found"}), 404
    
    filepath = file_record['filepath']
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

    if not filename.lower().endswith('.pdf'):
        return jsonify({"error": "Only PDF files are allowed"}), 400

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    filepath = os.path.join(folder_path, filename)
    try:
        await file.save(filepath)
        tool, description = handle_upload(filepath, os.path.splitext(filename)[0])
        tools.append(tool)
        insert_pdf_file(filename, filepath, description)
        all_files = get_all_files()
        return jsonify({"message": f"PDF {filename} uploaded successfully!"})
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"error": str(e)}), 500

@app.route("/delete", methods=["DELETE"])
async def delete_pdf(): 
    global tools, all_files
    form = await request.files

    if "file" not in form:
        return jsonify({"error": "No file provided"}), 400
    
    file = form["file"]
    filename = file.filename

    file_record = None
    for file in all_files:
        if(file['filename'] == filename):
            file_record = file

    if not file_record:
        return jsonify({"error": "File not found"}), 404

    file_path = file_record['filepath']
    try:
        os.remove(file_path)
        file_storage_context_path = os.path.join(storage_context_path, os.path.splitext(filename)[0])
        if os.path.isdir(file_storage_context_path):
            shutil.rmtree(file_storage_context_path, ignore_errors=True)

        delete_pdf_file(filename)
        delete_document(os.path.splitext(filename)[0])
        tools = [tool for tool in tools if tool.metadata.name != os.path.splitext(filename)[0]]
        all_files = get_all_files()
        return jsonify({"message": f"PDF {filename} deleted successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/query", methods=["GET"])
async def query_pdf():
    global tools, all_chats_messages
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
    for chat in all_chats_messages:
        if(chat['chat_id'] == int(id)):
            conversation = (chat['usermessage'], chat['botmessage'])
            chat_history.append(conversation)
    try:
        response, context = query_document(query, tools, chat_history)
        return jsonify({"response": response, "context": context})
    except Exception as e:
        return jsonify({"error": f"An error occurred while generating a response: {str(e)}"}), 500
    
# ---------------------------- Chat Routes ----------------------------

@app.route("/chats", methods=["GET"])
async def list_chats():
    global all_chats
    return jsonify({"chats": all_chats})

@app.route("/chats", methods=["POST"])
async def create_chat():
    global all_chats
    data = await request.get_json()
    name = data.get("name", "New chat")  
    
    try:
        chat_id = insert_chat(name)
        all_chats = get_all_chats()
        return jsonify({
            "message": "Chat created successfully", 
            "chat_id": chat_id,
            "chat_name": name
        })
    except Exception as e:
        return jsonify({"error": f"Failed to create chat: {str(e)}"}), 500

@app.route("/chats/<int:chat_id>", methods=["PUT"])
async def update_chat(chat_id):
    global all_chats
    data = await request.get_json()
    new_name = data.get("name")
    
    if not new_name:
        return jsonify({"error": "New name is required"}), 400
    
    try:
        updated_name = update_chat_name(chat_id, new_name)
        all_chats = get_all_chats()
        return jsonify({
            "message": "Chat renamed successfully",
            "chat_id": chat_id,
            "chat_name": updated_name
        })
    except Exception as e:
        return jsonify({"error": f"Failed to rename chat: {str(e)}"}), 500

@app.route("/chats/<int:chat_id>", methods=["DELETE"])
async def remove_chat(chat_id):
    global all_chats
    try:
        delete_chat(chat_id)
        all_chats = get_all_chats()
        return jsonify({"message": f"Chat {chat_id} and its messages deleted successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to delete chat: {str(e)}"}), 500

@app.route("/chats/<int:chat_id>/messages", methods=["GET"])
async def get_messages(chat_id):
    messages = []
    for chat_message in all_chats_messages:
        if(chat_message['chat_id'] == int(chat_id)):
            messages.append(chat_message)
    return jsonify({"messages": messages})

@app.route("/chats/messages", methods=["GET"])
async def get_all_messages():
    global all_chats_messages
    return jsonify({"all messages": all_chats_messages})

@app.route("/chats/<int:chat_id>/messages", methods=["POST"])
async def add_message(chat_id):
    global all_chats_messages
    data = await request.get_json()
    usermessage = data.get("usermessage")
    botmessage = data.get("botmessage")
    context = data.get("context")

    if not usermessage or not botmessage:
        return jsonify({"error": "Both usermessage and botmessage are required"}), 400
    try:
        message_id = insert_chat_message(chat_id, usermessage, botmessage, context)
        all_chats_messages = get_all_chat_messages()
        return jsonify({"message": "Message added successfully", "id": message_id})
    except Exception as e:
        return jsonify({"error": f"Failed to save message: {str(e)}"}), 500

@app.route("/chats/<int:chat_id>/messages", methods=["DELETE"])
async def delete_messages(chat_id):
    global all_chats_messages
    data = await request.get_json()
    message_id = data.get("id")
    try:
        delete_messages_after(message_id, chat_id)
        all_chats_messages = get_all_chat_messages()
        return jsonify({"message": "Messages successfully deleted"})
    except Exception as e:
        return jsonify({"error": f"Failed to save message: {str(e)}"}), 500