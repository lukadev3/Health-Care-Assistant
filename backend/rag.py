import os
import chromadb
import math
from llmsherpa.readers import LayoutPDFReader
from llama_index.core import Document
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import Settings
#from llama_index.llms.ollama import Ollama
#from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_index.core.query_engine import ToolRetrieverRouterQueryEngine, SubQuestionQueryEngine
from llama_index.core.objects import ObjectIndex
from llama_index.core.tools import QueryEngineTool
from llama_index.core import load_index_from_storage
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.agent.workflow import ReActAgent, ToolCallResult, AgentStream
from dotenv import load_dotenv
from utils import make_automerging_index_tool
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision,
)
from ragas.llms import LlamaIndexLLMWrapper
from ragas.embeddings import LlamaIndexEmbeddingsWrapper
from datasets import Dataset

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH")
STORAGE_CONTEXT_PATH = os.getenv("STORAGE_CONTEXT_PATH")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
EVALUATE_MODEL_NAME = os.getenv("EVALUATE_MODEL_NAME")
EMBEDDING_MODEL_NAME_OPENAI = os.getenv("EMBEDDING_MODEL_NAME_OPENAI")
LLM_MODEL_NAME_OPENAI = os.getenv("LLM_MODEL_NAME_OPENAI")
EVALUATE_MODEL_NAME_OPENAI = os.getenv("EVALUATE_MODEL_NAME_OPENAI")
BASE_URL = os.getenv("BASE_URL")
LLMSHERPA_API_URL = os.getenv("LLMSHERPA_API_URL")
API_KEY = os.getenv("API_KEY")
PROMPT = os.getenv("PROMPT")

#Settings.embed_model = OllamaEmbedding(model_name=EMBEDDING_MODEL_NAME, base_url=BASE_URL)
#Settings.llm = Ollama(model=LLM_MODEL_NAME, request_timeout=360, base_url=BASE_URL)
#evaluate_llm = Ollama(model=EVALUATE_MODEL_NAME, request_timeout=360, base_url=BASE_URL)

Settings.embed_model = OpenAIEmbedding(model=EMBEDDING_MODEL_NAME_OPENAI, api_key=API_KEY)
Settings.llm = OpenAI(model=LLM_MODEL_NAME_OPENAI, api_key=API_KEY)
evaluate_llm = OpenAI(model=EVALUATE_MODEL_NAME_OPENAI, api_key=API_KEY)

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

reader = LayoutPDFReader(LLMSHERPA_API_URL)

def load_query_tool(name: str, description: str) -> QueryEngineTool:
    """
    Load an existing index from ChromaDB and return a QueryEngineTool.

    Args:
        name (str): Name of the document collection.
        description (str): Short summary of the document content.

    Returns:
        QueryEngineTool: Tool used for querying the indexed documents.
    """
    chroma_collection = chroma_client.get_or_create_collection(name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        persist_dir=f"{STORAGE_CONTEXT_PATH}/{name}"
    )

    automerging_index = load_index_from_storage(storage_context=storage_context)
    return make_automerging_index_tool(automerging_index, name, description)


def handle_upload(file_path: str, name: str) -> tuple[QueryEngineTool, str]:
    """
    Handle PDF upload, parse document, build vector and summary indexes, and return a query tool.

    Args:
        file_path (str): Path to the uploaded PDF.
        name (str): Name/identifier for the document collection.

    Returns:
        tuple: (QueryEngineTool, document description summary)

    Raises:
        ValueError: If there is an error during processing.
    """
    try:
        documents = reader.read_pdf(path_or_url=file_path)
        full_text = documents.to_text()

        putanja = 'documents.txt'
        with open(putanja, 'w', encoding='utf-8') as f:
             f.write(full_text)          

        document = Document(text=full_text)

        node_parser = HierarchicalNodeParser.from_defaults(
            chunk_sizes=[2048, 1024, 256] 
        )

        all_nodes = node_parser.get_nodes_from_documents([document]) 
        leaf_nodes = get_leaf_nodes(all_nodes)

        chroma_collection = chroma_client.get_or_create_collection(name)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        batch_size = 166
        batches = [leaf_nodes[i:i+batch_size] for i in range(0, len(leaf_nodes), batch_size)]

        automerging_index = VectorStoreIndex(
            batches[0],
            storage_context=storage_context,
            use_async=True,
            show_progress=True
        )

        for i in range(1, len(batches)):
            automerging_index.insert_nodes(batches[i])
        
        storage_context.docstore.add_documents(all_nodes)
        storage_context.persist(persist_dir=f"{STORAGE_CONTEXT_PATH}/{name}")

        description_text = f"""This document provides comprehensive information about {name}.
                     It includes details on the intended use, recommended dosage, methods of administration, potential side effects, 
                     interactions with other drugs, contraindications, precautions, and safety guidelines. The document is intended to serve as a complete 
                     reference for understanding how {name} should be used, what benefits it offers, and what risks or 
                     considerations should be kept in mind. Additional information may include storage instructions, 
                     patient guidance, and clinical notes relevant to {name}."""
        
        return make_automerging_index_tool(automerging_index, name, description_text), description_text
    except Exception as e:
        error_msg = f"Error processing {name}: {str(e)}"
        print(error_msg)
        raise ValueError(error_msg) from e
    
def delete_document(name: str):
    """
    Delete a document collection from ChromaDB.

    Args:
        name (str): Name of the document collection to delete.
    """
    chroma_client.delete_collection(name)

async def query_document(query: str, tools: list, chat_history: list[tuple[str, str]]) -> tuple[str, list]:
    """
    Run a structured medical query against a set of tools using ToolRetrieverRouterQueryEngine.

    Args:
        query (str): User's medical query.
        tools (list): List of QueryEngineTools.
        chat_history (list[tuple[str, str]]): Prior conversation history.

    Returns:
        tuple: (answer string, list of context nodes used)
    """

    agent = ReActAgent(tools=tools, 
                       llm=Settings.llm, 
                       system_prompt=PROMPT,
                       name="MedicalReActAgent", 
                       description="An agent that answers medical queries using the provided tools only.")
    
    history_text = "\n".join([f"User: {user}\nAssistant: {assistant}" for user, assistant in chat_history])
    query = (
        f"Conversation history:\n{history_text}\n\n"
        f"Current user question:\n{query}\n"
    )
    try:
        handler = agent.run(query)
        context = []
        async for ev in handler.stream_events():
            if isinstance(ev, ToolCallResult):
                print(f"\nCall {ev.tool_name} with {ev.tool_kwargs}\nReturned: {ev.tool_output}")
                raw = getattr(ev.tool_output, 'raw_output', None)
                if raw and hasattr(raw, 'source_nodes'):
                    for node_score in raw.source_nodes:
                        node = getattr(node_score, 'node', None)
                        if node and hasattr(node, 'text'):
                            context.append(node.text)
            if isinstance(ev, AgentStream):
                print(f"{ev.delta}", end="", flush=True)

        response = await handler
        return str(response), context
    except Exception as e:
        return (
            "I encountered an error processing your request. "
            f"Please try rephrasing your question or ask about a different topic: {e}", []
        )

def evaluate_sample(question: str, context: list[str], answer: str, ground_truth: str):
    """
    Evaluates a single RAG sample using all available RAGAS metrics.

    Args:
        question (str): User question.
        context (list[str]): List of context passages retrieved by retriever.
        answer (str): LLM-generated answer.
        ground_truth (str): True/expected answer (if known).

    Returns:
        pd.DataFrame: Evaluation scores for each metric.
    """

    def clean_nan_values(d):
        return {
            k: (None if isinstance(v, float) and math.isnan(v) else v)
            for k, v in d.items()
        }

    data = {
        "question": [question],
        "contexts": [context],
        "answer": [answer],
        "ground_truth": [ground_truth]
    }

    dataset = Dataset.from_dict(data)

    result = evaluate(
        llm=LlamaIndexLLMWrapper(evaluate_llm),
        embeddings=LlamaIndexEmbeddingsWrapper(Settings.embed_model),
        dataset = dataset, 
        metrics=[
            context_precision,
            context_recall,
            faithfulness,
            answer_relevancy,
        ],
    )

    raw_result = result.to_pandas().T.to_dict()[0]
    return clean_nan_values(raw_result)


