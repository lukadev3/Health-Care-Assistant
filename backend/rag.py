import os
import chromadb
import asyncio
from llama_index.core import Document
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import SimpleDirectoryReader
from llama_index.core import Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.selectors import LLMMultiSelector
from llama_index.core.tools import QueryEngineTool
from llama_index.core import load_index_from_storage
from dotenv import load_dotenv
from utils import extract_text_from_pdf, make_tool

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH")
STORAGE_CONTEXT_PATH = os.getenv("STORAGE_CONTEXT_PATH")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
BASE_URL = os.getenv("BASE_URL")

Settings.embed_model =OllamaEmbedding(model_name=EMBEDDING_MODEL_NAME, base_url=BASE_URL)
Settings.llm = Ollama(model=LLM_MODEL_NAME, request_timeout=360, base_url=BASE_URL)

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

def load_query_tool(name: str, index_id: str) -> QueryEngineTool:

    """Load documents from ChromaDB and create QueryEngineTool."""

    chroma_collection = chroma_client.get_or_create_collection(name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        persist_dir=f"{STORAGE_CONTEXT_PATH}/{name}"
    )

    automerging_index = load_index_from_storage(index_id=index_id, storage_context=storage_context)
    return make_tool(automerging_index, name)


def handle_upload(file_path: str, name: str) -> QueryEngineTool:

    """Process uploaded PDF, create index and return QueryEngineTool."""

    documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
    document = Document(text="\n\n".join([doc.text for doc in documents]))

    chunk_sizes = [2048, 512, 128]
    node_parser = HierarchicalNodeParser.from_defaults(chunk_sizes=chunk_sizes)

    nodes = node_parser.get_nodes_from_documents([document])
    leaf_nodes = get_leaf_nodes(nodes)

    chroma_collection = chroma_client.get_or_create_collection(name)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    automerging_index = VectorStoreIndex(leaf_nodes, storage_context=storage_context)
    storage_context.docstore.add_documents(nodes)
    storage_context.persist(persist_dir=f"{STORAGE_CONTEXT_PATH}/{name}")

    return make_tool(automerging_index, name), automerging_index


def break_question_into_subquestions_llm(query: str) -> list[str]:

    """Break the query into subquestions using LLM, based on well-defined rules and examples."""

    prompt = f"""
        You are a helpful assistant. Your task is to break the following query into clear subquestions if there are multiple ones.

        ⚠️ VERY IMPORTANT RULES:
        - RESPOND ONLY WITH SUBQUESTIONS, separated by commas (this is a comma: ,)
        - DO NOT INVENT or REPHRASE questions.
        - KEEP the wording and structure similar to the user's input.
        - DO NOT add extra characters like new lines (\\n), bullets, quotes, or explanations — just return the subquestions separated by commas.
        - If there is only one question in the input, return only that question (possibly slightly cleaned).
        - Maintain the tone and grammar of the original question.
        - NEVER expand, shorten, or modify content.
        - If a second part of a question implicitly refers to the subject from the first part, make it explicit in the subquestion (repeat the subject).

        ### Examples of correct behavior:

        ✅ Input: Can you tell me about charging galaxy buds smr170 and how to connect huawei b660 on WIFI  
        ➡️ Output: Can you tell me about charging galaxy buds smr170,Can you tell me how to connect huawei b660 on WIFI

        ✅ Input: What is the battery life of JBL Charge 4 also how to reset it  
        ➡️ Output: What is the battery life of JBL Charge 4,How to reset JBL Charge 4

        ✅ Input: Can I use my smartwatch while charging and can I charge it overnight and will it overheat  
        ➡️ Output: Can I use my smartwatch while charging,Can I charge it overnight,Will it overheat

        ✅ Input: Why is my router blinking red  
        ➡️ Output: Why is my router blinking red

        ✅ Input: My galaxy buds do not work how to fix them  
        ➡️ Output: How to fix galaxy buds

        ✅ Input: Can I wash my headphones in water  
        ➡️ Output: Can I wash my headphones in water

        ✅ Input: Is Bose QC35 good for travel what is the noise cancelling like  
        ➡️ Output: Is Bose QC35 good for travel,What is the noise cancelling like

        ✅ Input: Can you tell me about charging JBL Live Pro 2 and how long it lasts on a single charge  
        ➡️ Output: Can you tell me about charging JBL Live Pro 2,How long does JBL Live Pro 2 last on a single charge

        Now apply these rules and examples to break the following query:
        {query}
        """

    response = Settings.llm.complete(prompt)

    subquestions_raw = str(response).strip()
    subquestions_clean = [q.strip() for q in subquestions_raw.split(",") if q.strip()]

    return subquestions_clean



def query_document(query: str, tools: list):

    """Answer the query using RouterQueryEngine with multiple tools."""

    subquestions = break_question_into_subquestions_llm(query)
    print(subquestions)

    for subquestion in subquestions:

        print(subquestion)

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

            f"User query: {subquestion}"
        )

        query_engine = RouterQueryEngine(
            selector=LLMMultiSelector.from_defaults(),  
            query_engine_tools=tools,
            verbose=True
        )

        try:
            message = ""
            response = query_engine.query(prompt)  
            for token in response.response_gen:  
                message += token
                print(token)
                yield token
            yield '\n'

        except Exception as e:
            return f"An error occurred while generating a response: {str(e)}"

def delete_document(name: str):

    """Delete a document from ChromaDB."""

    chroma_client.delete_collection(name)

