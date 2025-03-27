import re
import fitz
from llama_index.core import VectorStoreIndex, SummaryIndex
from llama_index.core.tools import QueryEngineTool, ToolMetadata

def clean_text(text):

    """Clean text by removing special characters."""

    text = re.sub(r"[^a-zA-Z0-9.,!? ]+", "", text)
    text = re.sub(r"\b\d{5,}\b", "", text)
    text = re.sub(r"\[.*?\]|\(.*?\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_text_from_pdf(file_path: str) -> str:

    """Extract text from a PDF file."""

    pdf_document = fitz.open(file_path)
    return clean_text(" ".join(page.get_text("text") for page in pdf_document))

def make_tools(vector_index: VectorStoreIndex, name: str, nodes: list):

    """Create vector and summary tools."""
    
    query_engine = vector_index.as_query_engine()
    vector_query_tool = QueryEngineTool(
        query_engine=query_engine,
        metadata=ToolMetadata(
            name=f"vector_tool_{name}",
            description=f"Answer specific questions related to {name}."
        ),
    )

    summary_index = SummaryIndex(nodes)
    summary_query_engine = summary_index.as_query_engine(response_mode="tree_summarize", use_async=True)
    summary_tool = QueryEngineTool(
        query_engine=summary_query_engine,
        metadata=ToolMetadata(
            name=f"summary_tool_{name}",
            description=f"Summarize information about {name}."
        ),
    )

    return vector_query_tool, summary_tool