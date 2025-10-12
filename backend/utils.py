from llama_index.core.tools import QueryEngineTool
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core import VectorStoreIndex
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.query_engine import RetrieverQueryEngine

def make_automerging_index_tool(index: VectorStoreIndex, name: str, description: str) -> QueryEngineTool:
    """Create a medical-optimized query tool that returns top relevant nodes."""

    retriever = AutoMergingRetriever(
        index.as_retriever(similarity_top_k=8),
        storage_context=index.storage_context,
        verbose=True
    )

    rerank = SentenceTransformerRerank(
        top_n=4,
        model="cross-encoder/ms-marco-MiniLM-L-6-v2"
    )

    query_engine = RetrieverQueryEngine.from_args(
        retriever=retriever,
        node_postprocessors=[rerank]
    )

    return QueryEngineTool.from_defaults(
        query_engine=query_engine,
        name=f"drug_{name}",
        description=f"{description}"
    )