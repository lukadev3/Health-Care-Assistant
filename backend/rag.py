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
from llama_index.core.query_engine import RouterQueryEngine, ToolRetrieverRouterQueryEngine
from llama_index.core.objects import ObjectIndex, SimpleToolNodeMapping, ObjectRetriever
from llama_index.core.selectors import LLMMultiSelector
from llama_index.core.tools import QueryEngineTool
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.memory import ChatMemoryBuffer
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
    description = query_engine.query("What is document about? Give me answer in four concise sentences.")
    print(description)

    return make_tool(automerging_index, name, str(description)), str(description)

def query_document(query: str, tools: list, chat_history: list[tuple[str, str]]) -> str:

    """Answer the query using ToolRetrieverRouterQueryEngine with multiple tools."""

    history_text = "\n".join([f"User: {user}\nAssistant: {assistant}" for user, assistant in chat_history])
    prompt = (
        "You are a licensed medical doctor and a professional assistant, specialized in pharmacology and drug usage.\n"
        "You have access to multiple specialized tools, each representing detailed documentation and clinical guidelines for a specific drug.\n"
        "Your role is to provide accurate, evidence-based, and easy-to-understand medical advice to patients and users based strictly on the contents of these tools.\n\n"

        "Guidelines for your answers:\n"
        "- Always use the full context of the conversation to understand what the user is referring to.\n"
        "- You must track the drug(s) mentioned earlier in the conversation to interpret follow-up questions correctly.\n"
        "- If the user asks a question like 'how should I use it' or 'does it have side effects', infer what 'it' refers to based on previous context.\n"
        "- Use **only the most relevant tool**, based on the most recently discussed or clearly referenced drug.\n"
        "- Do **not combine** information from multiple tools unless the user clearly mentions multiple drugs.\n"
        "- When a new drug is introduced, switch to that drug as the main context.\n"
        "- Do not speculate or answer outside the information found in the uploaded documents.\n"
        "- Avoid referencing tools or data sources by name—respond naturally, like a real doctor would.\n"
        "- Use clear, human-friendly language while maintaining professionalism and medical precision.\n"
        "- Always prioritize patient safety and clarity in communication.\n\n"

        f"history chat: {history_text}"

        f"query: {query}"
    )

    try:
        object_index = ObjectIndex.from_objects(
            tools, index_cls=VectorStoreIndex
        )        
        retriever = object_index.as_retriever()

        router_engine = ToolRetrieverRouterQueryEngine(
            retriever=retriever,
        )
        response = router_engine.query(prompt)
        print(response)
        return str(response)

    except Exception as e:
        return (
            "⚠️ I encountered an error processing your request. "
            f"Please try rephrasing your question or ask about a different topic: {e}"
        )
    
def delete_document(name: str):

    """Delete a document from ChromaDB."""

    chroma_client.delete_collection(name)

