from llama_index.core.tools import QueryEngineTool
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.query_engine import RetrieverQueryEngine

def make_tool(index: AutoMergingRetriever, name: str, description: str) -> QueryEngineTool:
    """Create a medical-optimized query tool"""
    retriever = AutoMergingRetriever(
        index.as_retriever(similarity_top_k=5),
        storage_context=index.storage_context,
        verbose=True
    )
    
    rerank = SentenceTransformerRerank(
        top_n=3,
        model="cross-encoder/ms-marco-MiniLM-L-6-v2"
    )
    
    query_engine = RetrieverQueryEngine.from_args(
        retriever,
        node_postprocessors=[rerank],
        streaming=True
    )
    
    return QueryEngineTool.from_defaults(
        query_engine=query_engine,
        name=f"drug_{name}",
        description=f"Clinical information about {name}. {description}",
    )