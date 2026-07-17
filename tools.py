import os
import google.generativeai as genai
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger("document-context-retrieval-system")

def retrieve_answer(query: str, document_id: Optional[str] = None) -> str:
    """
    Wraps the existing RAG pipeline to retrieve factual answers from the indexed documents.
    Use this tool whenever the user asks a question that requires searching the knowledge base.
    
    Args:
        query: The question or query to answer based on the document context.
        document_id: Optional specific document name to restrict the search to.
    """
    # Import locally to avoid circular dependency with main.py
    from main import QueryRequest, query_document
    
    request = QueryRequest(query=query, document_name=document_id)
    try:
        result = query_document(request)
        return result["answer"]
    except Exception as e:
        logger.error(f"Error in retrieve_answer tool: {str(e)}")
        return f"Error retrieving answer: {str(e)}"

def summarize_document(document_id: str) -> str:
    """
    Retrieves chunks across the whole document and produces a concise summary.
    Use this tool when the user asks for an overview or summary of a specific document.
    
    Args:
        document_id: The specific document name to summarize.
    """
    from main import get_services
    try:
        gemini_key, pc, pinecone_index = get_services()
        
        # Querying a generic vector to fetch top chunks for the document
        emb_resp = pc.inference.embed(
            model="llama-text-embed-v2",
            inputs=["introduction summary overview main topics"],
            parameters={"input_type": "query", "truncate": "END"}
        )
        query_embedding = emb_resp.data[0].values
        
        query_results = pinecone_index.query(
            vector=query_embedding,
            top_k=10,
            include_metadata=True,
            filter={"document_name": document_id}
        )
        
        matches = query_results.get("matches", [])
        if not matches:
            return f"No context found for document '{document_id}' to summarize."
            
        retrieved_contexts = [m.get("metadata", {}).get("text", "") for m in matches]
        context_str = "\n\n".join(retrieved_contexts)
        
        global last_summarize_context
        last_summarize_context = context_str
        
        model = genai.GenerativeModel(model_name="gemini-2.5-flash")
        prompt = f"Summarize the following document excerpts concisely:\n\n{context_str}"
        response = model.generate_content(prompt)
        
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error in summarize_document tool: {str(e)}")
        return f"Error summarizing document: {str(e)}"

def flag_low_confidence(faithfulness_score: float, threshold: float = 0.95) -> str:
    """
    Returns a warning flag/message if the Ragas faithfulness score for a response is below the threshold.
    This is an internal guardrail tool.
    
    Args:
        faithfulness_score: The calculated faithfulness score (0.0 to 1.0).
        threshold: The threshold below which the response is flagged. Defaults to 0.95.
    """
    if faithfulness_score < threshold:
        return f"WARNING: Low confidence detected (Score: {faithfulness_score:.2f} < {threshold}). The generated answer may contain hallucinations or ungrounded statements."
    return f"Confidence is high (Score: {faithfulness_score:.2f}). No flags raised."

def list_documents() -> str:
    """
    Returns the list of indexed documents and metadata currently available in the system.
    """
    from main import uploaded_documents
    
    if not uploaded_documents:
        return "No documents are currently indexed in the system."
        
    return "Indexed Documents:\n" + "\n".join([f"- {doc}" for doc in uploaded_documents])

# Export list of callable tools for Gemini
agent_tools = [
    retrieve_answer,
    summarize_document,
    flag_low_confidence,
    list_documents
]
