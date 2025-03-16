import os
import chromadb
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext, SummaryIndex
from llama_index.core.objects import ObjectIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.tools import QueryEngineTool
from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.agent import AgentRunner
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.mistralai import MistralAI
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from dotenv import load_dotenv

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

Settings.embed_model = HuggingFaceEmbedding(model_name=EMBEDDING_MODEL_NAME)
Settings.llm = MistralAI(model=LLM_MODEL_NAME, api_key=MISTRAL_API_KEY)

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
chroma_collection = chroma_client.get_or_create_collection("pdf_vectors")
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)


def handle_upload(file_path: str, name: str) -> str:
    """Get vector query and summary query tools from a document."""

    name = os.path.splitext(name)[0]
    
    documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
    splitter = SentenceSplitter(chunk_size=1024)
    nodes = splitter.get_nodes_from_documents(documents)

    vector_index = VectorStoreIndex(nodes, storage_context=storage_context)
    query_engine = vector_index.as_query_engine(
        similarity_top_k=3
    )
    vector_query_tool = QueryEngineTool.from_defaults(
        name=f"vector_tool_{name}",
        query_engine=query_engine,
        description=f"Useful for giving specific answer on question related to {name}"
    )

    summary_index = SummaryIndex(nodes)
    summary_query_engine = summary_index.as_query_engine(
        response_mode="tree_summarize",
        use_async=True,
    )
    summary_tool = QueryEngineTool.from_defaults(
        name=f"summary_tool_{name}",
        query_engine=summary_query_engine,
        description=f"Useful for summarization questions related to {name}"
    )

    return vector_query_tool, summary_tool


def query_tools(query: str, tools: dict) -> str:
    
    obj_index = ObjectIndex.from_objects(
        tools,
        index_cls=VectorStoreIndex,
    )

    obj_retriever = obj_index.as_retriever(similarity_top_k=3)

    agent_worker = FunctionCallingAgentWorker.from_tools(
        tool_retriever=obj_retriever,  
        llm = Settings.llm,
        system_prompt=""" \
            You are an agent designed to answer queries over a set of given papers.
            Please always use the tools provided to answer a question. Do not rely on prior knowledge.\
            """,
        verbose=True
    )
    agent = AgentRunner(agent_worker)
    
    response = agent.chat(query)
    return str(response)
