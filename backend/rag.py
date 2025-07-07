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
BASE_URL = os.getenv("BASE_URL")
LLMSHERPA_API_URL = os.getenv("LLMSHERPA_API_URL")

Settings.embed_model =OllamaEmbedding(model_name=EMBEDDING_MODEL_NAME, base_url=BASE_URL)
Settings.llm = Ollama(model=LLM_MODEL_NAME, request_timeout=360, base_url=BASE_URL)
evaluate_llm = Ollama(model=EVALUATE_MODEL_NAME, request_timeout=360, base_url=BASE_URL)

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

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
        reader = LayoutPDFReader(LLMSHERPA_API_URL)
        documents = reader.read_pdf(path_or_url=file_path)

        full_text = documents.to_text()
        document = Document(text=full_text)

        node_parser = HierarchicalNodeParser.from_defaults(
            chunk_sizes=[4116, 2058, 512] 
        )

        all_nodes = node_parser.get_nodes_from_documents([document]) 
        leaf_nodes = get_leaf_nodes(all_nodes)

        chroma_collection = chroma_client.get_or_create_collection(
            name,
            metadata={
                "hnsw:space": "cosine",
            }
        )
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

        summary_text = document.text[:2000]
        summary_doc = Document(text=summary_text)
        summary_index = SummaryIndex.from_documents([summary_doc]) 
        query_engine = summary_index.as_query_engine()
        description = query_engine.query("Give short summary of this drug.")
        print(description)
        description_text = str(description).strip()

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

def query_document(query: str, tools: list, chat_history: list[tuple[str, str]]) -> tuple[str, list]:
    """
    Run a structured medical query against a set of tools using ToolRetrieverRouterQueryEngine.

    Args:
        query (str): User's medical query.
        tools (list): List of QueryEngineTools.
        chat_history (list[tuple[str, str]]): Prior conversation history.

    Returns:
        tuple: (answer string, list of context nodes used)
    """
    history_text = "\n".join([f"User: {user}\nAssistant: {assistant}" for user, assistant in chat_history])
    prompt = (
        "You are a licensed medical doctor and professional assistant, specialized in pharmacology and drug usage.\n"
        "You have access to multiple specialized tools, each containing detailed documentation and clinical guidelines for a specific drug.\n"
        "Your role is to provide precise, evidence-based, and medically accurate advice to patients or users, strictly based on the contents of these tools.\n\n"

        "Important instructions:\n"
        "- Use ONLY the provided tools to answer the question. Do NOT rely on general knowledge or assumptions.\n"
        "- When the user asks a question, retrieve and present all directly relevant information from the tools.\n"
        "- Provide your answer in a clear and structured way, as a real doctor would explain to a patient.\n"
        "- Be detailed and thorough. If the information covers multiple aspects (e.g., dosage, warnings, age-specific instructions), include each part clearly.\n"
        "- If prior messages exist, always use that context to understand what the user is referring to.\n\n"

        "If your response includes a table, follow these rules strictly (it is not necessary for every one of your responses to include a table.):\n"
        "- Use GitHub-Flavored Markdown table syntax.\n"
        "- All rows must contain the same number of columns.\n"
        "- Do NOT leave any table cell empty. If a value is shared across multiple rows, repeat it in each row.\n"
        "- Do NOT merge or span cells — Markdown does not support it.\n"
        "- Do NOT use HTML tags. Instead, use Markdown line breaks: insert two spaces followed by a newline (e.g. `  \\n`) inside cells where multiple lines are needed.\n"
        "- Do NOT include bullet points or blank lines between table rows.\n"
        "- Format the table cleanly. Use `|` to separate each column, and a single `---` row after the headers.\n"
        "- Do NOT include any extra explanation, notes, or content before or after the table — output the table ONLY.\n\n"

        "Maintain a professional and helpful tone throughout the answer.\n\n"

        f"Conversation history:\n{history_text}\n\n"
        f"Current user question:\n{query}\n"
    )
    try:
        object_index = ObjectIndex.from_objects(
            tools, index_cls=VectorStoreIndex
        )        
        retriever = object_index.as_retriever()

        router_engine = ToolRetrieverRouterQueryEngine(
            retriever=retriever,
        )

        print(f"history: {history_text}, query: {query}")
        response = router_engine.query(prompt)
        print(response)
        context = [node.node.text for node in response.source_nodes]
        return str(response), context
    except Exception as e:
        return (
            "⚠️ I encountered an error processing your request. "
            f"Please try rephrasing your question or ask about a different topic: {e}", []
        )

def evaluate_sample(question: str, context: list[str], answer: str, ground_truth: str, llm, embeddings):
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

    data = {
        "question": [question],
        "contexts": [context],
        "answer": [answer],
        "ground_truth": [ground_truth]
    }

    dataset = Dataset.from_dict(data)

    result = evaluate(
        llm=LlamaIndexLLMWrapper(llm),
        embeddings=LlamaIndexEmbeddingsWrapper(embeddings),
        dataset = dataset, 
        metrics=[
            context_precision,
            context_recall,
            faithfulness,
            answer_relevancy,
        ],
    )

    return result.to_pandas().T


