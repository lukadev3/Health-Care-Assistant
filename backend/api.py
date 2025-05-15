import os
import asyncio
from quart import Quart, request, jsonify, Response
from rag import handle_upload, query_document, load_query_tool, delete_document
from database import init_db, insert_pdf_file, get_file, delete_pdf_file, get_all_files
from dotenv import load_dotenv

import nest_asyncio
nest_asyncio.apply()

load_dotenv()
init_db()  

folder_path = os.getenv("FOLDER_PATH")
app = Quart(__name__)

tools = []
all_files = []

async def load_tools_in_background():
    global tools, all_files
    all_files = get_all_files()

    for file in all_files:
        filename = os.path.splitext(file["filename"])[0]
        index_id = file["index_id"]
        try:
            tool = await asyncio.to_thread(load_query_tool, filename, index_id)
            tools.append(tool)
            print(f"Tool loaded for {filename}")
        except Exception as e:
            print(f"Failed to load tool for {filename}: {e}")


@app.before_serving
async def startup():
    asyncio.create_task(load_tools_in_background())

@app.route("/upload", methods=["POST"])
async def upload_pdf():
    global tools
    form = await request.files  

    if "file" not in form:
        return jsonify({"error": "No file provided"}), 400
    
    file = form["file"]
    filename = file.filename 

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    filepath = os.path.join(folder_path, filename)
    await file.save(filepath)

    filename = os.path.splitext(filename)[0]
    tool, index_id = handle_upload(filepath, filename)
    tools.append(tool)
    insert_pdf_file(filename, filepath, index_id)

    return jsonify({"message": f"PDF {filename} uploaded successfully!"})

@app.route("/delete", methods=["DELETE"])
async def delete_pdf(): 
    form = await request.files

    if "file" not in form:
        return jsonify({"error": "No file provided"}), 400
    
    file = form["file"]
    filename = os.path.splitext(file.filename)[0]
    
    delete_pdf_file(filename)
    delete_document(filename)
    _, file_path, _ = get_file(filename)
    os.remove(file_path) 

    return jsonify({"message": f"PDF {filename} deleted successfully!"})

@app.route("/query", methods=["GET"])
async def query_pdf():
    global tools
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Query is required"}), 400
    
    if len(tools) < len(all_files):
        return jsonify({
            "status": "loading",
            "message": "Tools are still loading. Please try again shortly."
        }), 503

    def generate():
        for token in query_document(query, tools):
            yield token

    return Response(generate(), content_type='text/plain')

if __name__ == "__main__":
    app.run(debug=True)