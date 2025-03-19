import re
import fitz
from llama_index.core import VectorStoreIndex, SummaryIndex
from llama_index.core.tools import QueryEngineTool

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