import os
import chromadb
from llama_index.core.schema import TextNode
from llama_index.core import Document
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.agent import AgentRunner, ReActAgentWorker
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import Settings
from llama_index.core.objects import ObjectIndex
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from dotenv import load_dotenv
from utils import extract_text_from_pdf, make_tools

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
BASE_URL = os.getenv("BASE_URL")

Settings.embed_model =OllamaEmbedding(model_name=EMBEDDING_MODEL_NAME, base_url=BASE_URL)
Settings.llm = Ollama(model=LLM_MODEL_NAME, request_timeout=360, base_url=BASE_URL)

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

def load_tools(name: str):

    """Load documents from ChromaDB and create tools from them."""

    chroma_collection = chroma_client.get_or_create_collection(name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    index = VectorStoreIndex.from_vector_store(
        vector_store
    )
    data = chroma_collection.get()
    nodes = [TextNode(text=doc) for doc in data["documents"]]
    
    vector_query_tool, summary_tool = make_tools(index, name, nodes)
    return vector_query_tool, summary_tool



def handle_upload(file_path: str, name: str):

    """Process uploaded PDF and create tools."""
    
    full_text = extract_text_from_pdf(file_path)
    
    document = Document(text=full_text)
    splitter = SentenceSplitter(chunk_size=1024)
    nodes = splitter.get_nodes_from_documents([document])

    chroma_collection = chroma_client.get_or_create_collection(name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(
        nodes, storage_context=storage_context
    )
    vector_query_tool, summary_tool = make_tools(index, name, nodes)
    return vector_query_tool, summary_tool


def query_tools(query: str, tools: list):

    """Query the tools using an agent."""

    obj_index = ObjectIndex.from_objects(
        tools,
        index_cls=VectorStoreIndex,
    )

    obj_retriever = obj_index.as_retriever(similarity_top_k=2)

    agent_worker = ReActAgentWorker.from_tools(
        tool_retriever=obj_retriever,
        llm=Settings.llm,
        verbose=True,
        system_prompt="Use only the provided tools to answer document-related queries."
    )
    agent = AgentRunner(agent_worker)
    response = agent.chat(query)
    print(str(response))

    return str(response)

def delete_document(name: str):

    """Delete a document from ChromaDB."""

    chroma_client.delete_collection(name)

