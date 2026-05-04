import math

from langchain_chroma import Chroma
from langchain_core.documents import Document

from rag_app import config


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class VectorStoreService(object):
    def __init__(self, embedding, user_id: str | None = None):
        self.embedding = embedding
        self.vector_store = Chroma(
            **config.build_chroma_kwargs(
                collection_name=config.build_user_collection_name(user_id),
                embedding_function=self.embedding,
            )
        )

    def retrieve_documents(self, query: str) -> list[Document]:
        scored_documents = self.similarity_search_with_scores(
            query,
            k=config.RETRIEVAL_FETCH_K,
        )
        filtered_documents = self.apply_similarity_threshold(scored_documents)
        diversified_documents = self.apply_mmr(query, filtered_documents)
        return diversified_documents[:config.MMR_CANDIDATE_K]

    def similarity_search_with_scores(self, query: str, k: int) -> list[Document]:
        scored_results = self.vector_store.similarity_search_with_relevance_scores(query, k=k)
        return [self.with_similarity_score(document, score) for document, score in scored_results]

    def apply_similarity_threshold(self, documents: list[Document]) -> list[Document]:
        if not config.SIMILARITY_THRESHOLD_ENABLED:
            return documents

        return [
            document
            for document in documents
            if float(document.metadata.get("similarity_score", 0.0)) >= config.SIMILARITY_THRESHOLD
        ]

    def apply_mmr(self, query: str, documents: list[Document]) -> list[Document]:
        if not documents:
            return []

        candidate_limit = min(len(documents), max(config.MMR_CANDIDATE_K, config.RETRIEVAL_TOP_K))
        if not config.MMR_ENABLED or len(documents) <= 1:
            return documents[:candidate_limit]

        query_embedding = self.embedding.embed_query(query)
        document_embeddings = self.embedding.embed_documents(
            [document.page_content for document in documents]
        )
        query_similarities = [
            cosine_similarity(query_embedding, document_embedding)
            for document_embedding in document_embeddings
        ]

        selected_indices: list[int] = []
        remaining_indices = list(range(len(documents)))

        while remaining_indices and len(selected_indices) < candidate_limit:
            if not selected_indices:
                next_index = max(remaining_indices, key=lambda index: query_similarities[index])
            else:
                next_index = max(
                    remaining_indices,
                    key=lambda index: (
                        config.MMR_LAMBDA_MULT * query_similarities[index]
                        - (1 - config.MMR_LAMBDA_MULT)
                        * max(
                            cosine_similarity(document_embeddings[index], document_embeddings[selected_index])
                            for selected_index in selected_indices
                        )
                    ),
                )

            selected_indices.append(next_index)
            remaining_indices.remove(next_index)

        mmr_documents = []
        for rank, index in enumerate(selected_indices, start=1):
            document = documents[index]
            document.metadata["mmr_rank"] = rank
            mmr_documents.append(document)
        return mmr_documents

    @staticmethod
    def with_similarity_score(document: Document, score: float) -> Document:
        metadata = dict(document.metadata)
        metadata["similarity_score"] = round(float(score), 4)
        return Document(page_content=document.page_content, metadata=metadata)
