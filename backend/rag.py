import os
import chromadb
import fitz
import tempfile
import re
from llama_index.core.schema import TextNode
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext, SummaryIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.tools import QueryEngineTool
from llama_index.core.agent import ReActAgent
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from dotenv import load_dotenv

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")

Settings.embed_model = HuggingFaceEmbedding(model_name=EMBEDDING_MODEL_NAME)
Settings.llm = None #MORA DA SE NADJI NEKI LLM

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
chroma_collection = chroma_client.get_or_create_collection("documents")
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

def clean_text(text):

    """Clean the text by removing special characters."""

    text = re.sub(r"[^a-zA-Z0-9.,!? ]+", "", text)
    text = re.sub(r"\b\d{5,}\b", "", text)
    text = re.sub(r"\[.*?\]|\(.*?\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    
    return text

def extract_text_from_pdf(file_path: str) -> str:

    """Extract text from the PDF file using PyMuPDF."""

    pdf_document = fitz.open(file_path)
    full_text = ""
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        full_text += page.get_text("text")  
    full_text = clean_text(full_text)
    return full_text

def make_tools(vector_index: VectorStoreIndex, name: str, nodes: list):

    """Create tools from the vector index and summary index."""

    query_engine = vector_index.as_query_engine(similarity_top_k=2)
    vector_query_tool = QueryEngineTool.from_defaults(
        name=f"vector_tool_{name}",
        query_engine=query_engine,
        description=f"Useful for giving specific answer on question related to {name}"
    )
    
    summary_index = SummaryIndex(nodes)
    summary_query_engine = summary_index.as_query_engine(response_mode="tree_summarize")
    summary_tool = QueryEngineTool.from_defaults(
        name=f"summary_tool_{name}",
        query_engine=summary_query_engine,
        description=f"Useful for summarization questions related to {name}"
    )
    return vector_query_tool, summary_tool

def load_tools(name: str):

    """Load nodes from ChromaDB and create tools from them."""

    name = os.path.splitext(name)[0]

    vector_index = VectorStoreIndex.from_vector_store(vector_store)

    total_docs = len(chroma_collection.get()["ids"])
    query_results = chroma_collection.get(
        ids=[f"{name}_{i}" for i in range(total_docs)]
    )
    if not query_results["documents"]:
        raise ValueError(f"No documents found for {name} in ChromaDB.")

    nodes = [TextNode(text=doc) for doc in query_results["documents"]]

    vector_query_tool, summary_tool = make_tools(vector_index, name, nodes)
    return vector_query_tool, summary_tool


def handle_upload(file_path: str, name: str):
       
    """Handle the uploaded PDF file and create tools from it."""

    name = os.path.splitext(name)[0]

    full_text = extract_text_from_pdf(file_path)

    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as temp_file:
        temp_file.write(full_text)
        temp_file_path = temp_file.name

    documents = SimpleDirectoryReader(input_files=[temp_file_path]).load_data()
    splitter = SentenceSplitter(chunk_size=1024)
    nodes = splitter.get_nodes_from_documents(documents)

    embeddings = [Settings.embed_model.get_text_embedding(node.text) for node in nodes]

    chroma_collection.add(
        embeddings=embeddings,
        ids=[f"{name}_{i}" for i in range(len(nodes))],
        metadatas=[{"source": name}] * len(nodes),
        documents=[node.text for node in nodes]
    )

    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    vector_index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)

    vector_query_tool, summary_tool = make_tools(vector_index, name, nodes)
    return vector_query_tool, summary_tool


def query_tools(query: str, tools: dict) -> str:

    """Create an agent from the tools and query the agent with the query."""
    
    agent = ReActAgent.from_tools(
        tools=tools,  
        llm=Settings.llm,
        system_prompt=""" \
            You are an agent designed to answer queries using the available tools.
            Always respond with the tools provided and do not rely on prior knowledge. 
            Use the most relevant tool to answer the user's question.\
            """,
        verbose=True
    )
    response = agent.query(query)
    return str(response)
