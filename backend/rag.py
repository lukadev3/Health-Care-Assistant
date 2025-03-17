import os
import chromadb
import fitz
import tempfile
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext, SummaryIndex, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.tools import QueryEngineTool
from llama_index.core.agent import ReActAgent
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
#from llama_index.llms.huggingface import HuggingFaceLLM
from llama_index.llms.huggingface_api import HuggingFaceInferenceAPI
from dotenv import load_dotenv

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
API_TOKEN = os.getenv("API_TOKEN")

Settings.embed_model = HuggingFaceEmbedding(model_name=EMBEDDING_MODEL_NAME)
Settings.llm = HuggingFaceInferenceAPI(model_name=LLM_MODEL_NAME, token=API_TOKEN)

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
chroma_collection = chroma_client.get_or_create_collection("pdf_vectors")
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

def extract_text_from_pdf(file_path: str) -> str:

    """Extract text from the PDF file using PyMuPDF."""
    pdf_document = fitz.open(file_path)
    full_text = ""
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        full_text += page.get_text("text")  
    print(full_text)
    return full_text


def handle_upload(file_path: str, name: str) -> str:
    
    """Get vector query and summary query tools from a document.
       If indexes for related file exist, function load them and make vector and summary tools.
       Otherwise, create indexes and tools from the file."""
    
    name = os.path.splitext(name)[0]
    
    try: 
        vector_index = load_index_from_storage(storage_context, f"vector_index_{name}") 
        summary_index = load_index_from_storage(storage_context, f"summary_index_{name}")
        vector_query_tool = QueryEngineTool.from_defaults(
            name=f"vector_tool_{name}",
            query_engine=vector_index.as_query_engine(
                similarity_top_k=3
            ),
            description=f"Useful for giving specific answer on question related to {name}"
        )
        summary_tool = QueryEngineTool.from_defaults(
            name=f"summary_tool_{name}",
            query_engine=summary_index.as_query_engine(
                response_mode="tree_summarize",
            ),
            description=f"Useful for summarization questions related to {name}"
        )
    except:
        full_text = extract_text_from_pdf(file_path)
        
        with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as temp_file:
            temp_file.write(full_text)
            temp_file_path = temp_file.name

        documents = SimpleDirectoryReader(input_files=[temp_file_path]).load_data()
        splitter = SentenceSplitter(chunk_size=1024)
        nodes = splitter.get_nodes_from_documents(documents)

        vector_index = VectorStoreIndex(nodes, storage_context=storage_context)
        vector_index.set_index_id(f"vector_index_{name}")
        
        query_engine = vector_index.as_query_engine(
            similarity_top_k=3
        )
        vector_query_tool = QueryEngineTool.from_defaults(
            name=f"vector_tool_{name}",
            query_engine=query_engine,
            description=f"Useful for giving specific answer on question related to {name}"
        )

        summary_index = SummaryIndex(nodes, storage_context=storage_context)
        summary_index.set_index_id(f"summary_index_{name}")
        summary_query_engine = summary_index.as_query_engine(
            response_mode="tree_summarize"
        )
        summary_tool = QueryEngineTool.from_defaults(
            name=f"summary_tool_{name}",
            query_engine=summary_query_engine,
            description=f"Useful for summarization questions related to {name}"
        )

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
