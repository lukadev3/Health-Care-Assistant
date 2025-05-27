import re
import fitz
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.tools import QueryEngineTool, ToolMetadata

def clean_text(text: str) -> str:

    """Clean and normalize text for better semantic indexing."""

    # Remove long numbers (IDs, phone numbers, etc.)
    text = re.sub(r'\b\d{5,}\b', '', text)

    # Remove content in brackets or parentheses (e.g., references, inline notes)
    text = re.sub(r'\[.*?\]|\(.*?\)', '', text)

    # Remove unwanted characters but keep common punctuation
    text = re.sub(r'[^a-zA-Z0-9.,!?;:\'\-\s]', '', text)

    # Fix hyphenated words broken by line breaks
    text = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', text)

    # Replace multiple spaces/newlines with a single space
    text = re.sub(r'\s+', ' ', text)

    # Normalize text (optional: lowercase for consistency)
    text = text.strip()

    return text

def extract_text_from_pdf(file_path: str) -> str:

    """Extract and clean text from a PDF file."""
    pdf_document = fitz.open(file_path)
    full_text = []

    for page in pdf_document:
        text = page.get_text("text")
        cleaned = clean_text(text)
        if cleaned:  # Avoid appending empty strings
            full_text.append(cleaned)

    return " ".join(full_text)

def make_tool(automerging_index: AutoMergingRetriever, name: str, description: str, similarity_top_k=6, top_n=2) -> QueryEngineTool:
    """Making QueryEngineTool from index."""

    base_retriever = automerging_index.as_retriever(similarity_top_k=similarity_top_k)
    retriever = AutoMergingRetriever(
        base_retriever, automerging_index.storage_context, verbose=True
    )
    rerank = SentenceTransformerRerank(top_n=top_n)

    query_engine = RetrieverQueryEngine.from_args(
        retriever, node_postprocessors=[rerank], use_async=True
    )

    tool = QueryEngineTool(
        query_engine=query_engine,
        metadata=ToolMetadata(
            name=name,
            description=f"Tool for querying {name} data."
        )
    )
    return tool