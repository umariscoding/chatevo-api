"""
Custom Pinecone retriever implementation.
Uses shared index with namespace isolation per company.
"""

from typing import List, Any, Optional
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from pydantic import Field


class DirectPineconeRetriever(BaseRetriever):
    """
    Custom retriever that uses direct Pinecone queries for reliable document retrieval.
    Uses namespace isolation for multi-tenancy.
    Always returns results from the company's namespace, even if similarity is low.
    """

    pinecone_index: Any = Field(description="Pinecone index object")
    embedding_function: Any = Field(description="Embedding function")
    namespace: str = Field(description="Pinecone namespace (company_id)")
    top_k: int = Field(default=8, description="Number of documents to retrieve")
    min_results: int = Field(default=3, description="Minimum number of results to return")

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        Retrieve documents relevant to the query.
        ALWAYS returns results from the company's namespace, even if similarity is low.
        """
        try:
            # Generate embedding for the query
            query_embedding = self.embedding_function.embed_query(query)

            # Query Pinecone with explicit namespace for company isolation
            # This ensures we only get documents from this company's namespace
            results = self.pinecone_index.query(
                vector=query_embedding,
                top_k=self.top_k,
                namespace=self.namespace,  # Explicit namespace for company isolation
                include_metadata=True,
                filter={"company_id": self.namespace}  # Additional metadata filter
            )

            # Convert results to LangChain documents
            documents = []
            for match in results.matches:
                if hasattr(match, "metadata") and match.metadata:
                    text = match.metadata.get("text", "")
                    if text.strip():  # Only add non-empty documents
                        doc = Document(
                            page_content=text,
                            metadata={
                                **match.metadata,
                                "score": (
                                    match.score if hasattr(match, "score") else 0.0
                                ),
                            },
                        )
                        documents.append(doc)

            # If we got fewer results than min_results, try to get more by increasing top_k
            if len(documents) < self.min_results and len(documents) > 0:
                # We have some results, return them
                return documents
            elif len(documents) == 0:
                # No results found, try with higher top_k to ensure we get something
                fallback_results = self.pinecone_index.query(
                    vector=query_embedding,
                    top_k=self.top_k * 3,  # Try 3x the normal amount
                    namespace=self.namespace,
                    include_metadata=True,
                    filter={"company_id": self.namespace}
                )

                for match in fallback_results.matches:
                    if hasattr(match, "metadata") and match.metadata:
                        text = match.metadata.get("text", "")
                        if text.strip():
                            doc = Document(
                                page_content=text,
                                metadata={
                                    **match.metadata,
                                    "score": (
                                        match.score if hasattr(match, "score") else 0.0
                                    ),
                                },
                            )
                            documents.append(doc)
                            if len(documents) >= self.min_results:
                                break

            # Return whatever we found, even if similarity is low
            # This ensures the RAG always has context to work with
            return documents

        except Exception as e:
            # Log error but don't fail silently
            # Return empty list only on critical errors
            import logging
            logging.error(f"Error in retriever: {str(e)}")
            return []


def create_company_retriever(
    pinecone_index: Any,
    embedding_function: Any,
    namespace: str,
    top_k: int = 8,
    min_results: int = 3
) -> DirectPineconeRetriever:
    """
    Create a custom retriever for a company.
    Uses shared index with namespace isolation.
    Always returns results from the company's namespace.

    Args:
        pinecone_index: Pinecone index instance (shared index)
        embedding_function: Embedding function
        namespace: Company namespace (company_id)
        top_k: Number of documents to retrieve
        min_results: Minimum results to return (defaults to 3)

    Returns:
        Direct Pinecone retriever instance
    """
    return DirectPineconeRetriever(
        pinecone_index=pinecone_index,
        embedding_function=embedding_function,
        namespace=namespace,
        top_k=top_k,
        min_results=min_results,
    )