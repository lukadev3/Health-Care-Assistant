import os
import chromadb
from llama_cloud import MessageRole
from llama_index.core import Document
from llama_index.core import VectorStoreIndex, StorageContext, SummaryIndex
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import SimpleDirectoryReader
from llama_index.core import Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_index.core.query_engine import RouterQueryEngine, SubQuestionQueryEngine
from llama_index.core.selectors import LLMMultiSelector
from llama_index.core.tools import QueryEngineTool
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.chat_engine import CondenseQuestionChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.chat_engine.types import ChatMessage
from llama_index.core.prompts import PromptTemplate
import logging
from llama_index.core import load_index_from_storage
from dotenv import load_dotenv
from utils import extract_text_from_pdf, clean_text, make_tool

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH")
STORAGE_CONTEXT_PATH = os.getenv("STORAGE_CONTEXT_PATH")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
BASE_URL = os.getenv("BASE_URL")

#Settings.embed_model =OllamaEmbedding(model_name=EMBEDDING_MODEL_NAME, base_url=BASE_URL)
Settings.embed_model =HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
Settings.llm = Ollama(model=LLM_MODEL_NAME, request_timeout=360, base_url=BASE_URL)

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

def load_query_tool(name: str, description: str) -> QueryEngineTool:

    """Load documents from ChromaDB and create QueryEngineTool."""

    chroma_collection = chroma_client.get_or_create_collection(name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        persist_dir=f"{STORAGE_CONTEXT_PATH}/{name}"
    )

    automerging_index = load_index_from_storage(storage_context=storage_context)
    return make_tool(automerging_index, name, description)


def handle_upload(file_path: str, name: str) -> QueryEngineTool:

    """Process uploaded PDF, create index and return QueryEngineTool."""

    full_text = extract_text_from_pdf(file_path)
    cleaned_text = clean_text(full_text)

    #print(file_path, name)

    #documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
    #document = Document(text="\n\n".join([doc.text for doc in documents]))
    document = Document(text=cleaned_text)

    chunk_sizes = [2048, 512, 128]
    node_parser = HierarchicalNodeParser.from_defaults(chunk_sizes=chunk_sizes)

    nodes = node_parser.get_nodes_from_documents([document])
    leaf_nodes = get_leaf_nodes(nodes)

    chroma_collection = chroma_client.get_or_create_collection(name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    automerging_index = VectorStoreIndex(leaf_nodes, storage_context=storage_context, use_async=True)
    summary_index = SummaryIndex.from_documents([document])
    storage_context.docstore.add_documents(nodes)
    storage_context.persist(persist_dir=f"{STORAGE_CONTEXT_PATH}/{name}")

    query_engine = summary_index.as_query_engine()
    description = query_engine.query("Give me summary of this document.")
    print(description)

    return make_tool(automerging_index, name, str(description)), str(description)

def query_document(query: str, tools: list, chat_history: list[tuple[str, str]]) -> str:

    """Answer the query using SubQuestionQueryEngine with multiple tools."""

    history_text = "\n".join([f"User: {user}\nAssistant: {assistant}" for user, assistant in chat_history])

    prompt = (
        "You are a helpful assistant specialized in interpreting drug manuals.\n"
        "You have access to multiple specialized tools, each containing detailed information about a specific drug.\n"
        "When answering, use only the most relevant tool based on the **latest drug** mentioned in the conversation.\n"
        "If the user asks a follow-up question like 'how should I use it', assume 'it' refers strictly to the most recently discussed drug or topic.\n"
        "Do NOT combine answers from multiple tools unless the current question explicitly mentions multiple drugs.\n"
        "If the user mentions a new drug, switch tools accordingly and treat it as the new context.\n"
        "Ignore earlier topics unless they are clearly referenced again by the user.\n"
        "Always explain your answer in a clear, detailed, and natural way, as if you're helping someone without medical expertise.\n\n"
        "Here is the previous conversation for context:\n"
        f"{history_text}\n\n"
        "Now answer the following user query:\n"
        f"{query}\n"
    )



    try:
        sub_engine = SubQuestionQueryEngine.from_defaults(query_engine_tools=tools)
        response = sub_engine.query(prompt)
        return str(response)

    except Exception as e:
        return (
            "⚠️ I encountered an error processing your request. "
            f"Please try rephrasing your question or ask about a different topic: {e}"
        )
    
def delete_document(name: str):

    """Delete a document from ChromaDB."""

    chroma_client.delete_collection(name)

