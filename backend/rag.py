import os
import chromadb
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
    summary_index = SummaryIndex(leaf_nodes)
    storage_context.docstore.add_documents(nodes)
    storage_context.persist(persist_dir=f"{STORAGE_CONTEXT_PATH}/{name}")

    query_engine = summary_index.as_query_engine()
    description = query_engine.query("Give me summary of this document.")
    print(description)

    return make_tool(automerging_index, name, str(description)), str(description)

def query_document(query: str, tools: list):

    """Answer the query using SubQuestionQueryEngine with multiple tools."""

    prompt = (
        "You are a helpful and knowledgeable assistant specialized in interpreting technical manuals and product documentation. "
        "You have access to specialized tools containing all relevant information, and you must rely solely on those tools to answer user questions.\n\n"

        "Your goal is to provide clear, detailed, and human-like responses that are easy to understand, even for non-experts. "
        "Always use the tools to extract accurate answers and expand them with context when possible. Make your explanations thorough but natural, as if you’re speaking to someone who needs help understanding a product.\n\n"

        "⚠️ Important rules:\n"
        "- Use ONLY the tools to find answers — do not guess or invent anything.\n"
        "- DO NOT reference where you found the answer (no section names, no document IDs).\n"
        "- DO NOT respond with short or vague answers — always expand with helpful context, examples, or related tips.\n"
        "- Always sound polite, calm, and confident — like a real person helping another.\n"
        "- If you can make bullets for better understanding.\n"
        "- If the answer cannot be found using the tools, say: "
        "'I'm sorry, I couldn't find the answer to that based on the available information. Do you maybe have another question related to this product?'\n\n"
        
        "✅ If there is additional information from the tools that might help the user ask a better question or understand the product more deeply, "
        "politely ask the user if they would like to hear about it.\n\n"

        f"User query: {query}"
    )  

    try:
        query_engine = SubQuestionQueryEngine.from_defaults(
            query_engine_tools=tools
        )
        response = query_engine.query(prompt)
        return str(response)
        
    except Exception as e:
        return ("⚠️ I encountered an error processing your request. "
               "Please try rephrasing your question or ask about a different topic.")
    
def delete_document(name: str):

    """Delete a document from ChromaDB."""

    chroma_client.delete_collection(name)

