import os
import chromadb
from llmsherpa.readers import LayoutPDFReader
from llama_index.core import Document
from llama_index.core import VectorStoreIndex, StorageContext, SummaryIndex
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_index.core.query_engine import ToolRetrieverRouterQueryEngine
from llama_index.core.objects import ObjectIndex
from llama_index.core.tools import QueryEngineTool
from llama_index.core import load_index_from_storage
from dotenv import load_dotenv
from utils import make_tool

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH")
STORAGE_CONTEXT_PATH = os.getenv("STORAGE_CONTEXT_PATH")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
BASE_URL = os.getenv("BASE_URL")
LLMSHERPA_API_URL = os.getenv("LLMSHERPA_API_URL")

Settings.embed_model =OllamaEmbedding(model_name=EMBEDDING_MODEL_NAME, base_url=BASE_URL)
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


def handle_upload(file_path: str, name: str) -> tuple[QueryEngineTool, str]:
    """Process uploaded PDF in smaller batches with enhanced error handling"""
    try:

        reader = LayoutPDFReader(LLMSHERPA_API_URL)
        documents = reader.read_pdf(path_or_url=file_path)

        full_text = documents.to_text()

        max_chunk_size = 500 
        text_chunks = [full_text[i:i+max_chunk_size] for i in range(0, len(full_text), max_chunk_size)]
        chunked_documents = [Document(text=chunk) for chunk in text_chunks]

        node_parser = HierarchicalNodeParser.from_defaults(
            chunk_sizes=[1024, 512, 128] 
        )

        all_nodes = []
        for i in range(0, len(chunked_documents), 1):
            batch_docs = chunked_documents[i:i+1]
            nodes = node_parser.get_nodes_from_documents(batch_docs)
            all_nodes.extend(nodes)
        
        leaf_nodes = get_leaf_nodes(all_nodes)

        chroma_collection = chroma_client.get_or_create_collection(
            name,
            metadata={
                "hnsw:space": "cosine",
            }
        )
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        batch_size = 160
        batches = [leaf_nodes[i:i+batch_size] for i in range(0, len(leaf_nodes), batch_size)]

        automerging_index = VectorStoreIndex(
            batches[0],
            storage_context=storage_context,
            use_async=True,
            show_progress=True
        )

        for i in range(1, len(batches)):
            automerging_index.insert_nodes(batches[i])
        
        summary_index = SummaryIndex.from_documents([chunked_documents[0]])
        storage_context.docstore.add_documents(all_nodes)
        storage_context.persist(persist_dir=f"{STORAGE_CONTEXT_PATH}/{name}")

        query_engine = summary_index.as_query_engine()
        description = query_engine.query("Give short summary of this drug.")
        print(description)
        description_text = str(description).strip()

        return make_tool(automerging_index, name, description_text), description_text

    except Exception as e:
        error_msg = f"Error processing {name}: {str(e)}"
        print(error_msg)
        raise ValueError(error_msg) from e

def query_document(query: str, tools: list, chat_history: list[tuple[str, str]]) -> str:

    """Answer the query using ToolRetrieverRouterQueryEngine with multiple tools."""

    history_text = "\n".join([f"User: {user}\nAssistant: {assistant}" for user, assistant in chat_history])
    prompt = (
        "You are a licensed medical doctor and a professional assistant, specialized in pharmacology and drug usage.\n"
        "You have access to multiple specialized tools, each representing detailed documentation and clinical guidelines for a specific drug.\n"
        "Your role is to provide accurate, evidence-based, and easy-to-understand medical advice to patients and users based strictly on the contents of these tools.\n\n"
        "USE ONLY PROVIDED TOOLS TO ANSWER THE QUESTION!!!\n\n"

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

