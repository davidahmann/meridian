from abc import ABC, abstractmethod
from typing import List, Optional, Any
import os
import structlog
import asyncio
from openai import AsyncOpenAI
from openai import RateLimitError, APIError

logger = structlog.get_logger()


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embeds a list of texts."""
        pass

    @abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        """Embeds a single query."""
        pass


class OpenAIEmbedding(EmbeddingProvider):
    def __init__(
        self, model: str = "text-embedding-3-small", api_key: Optional[str] = None
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning(
                "OPENAI_API_KEY not found. Embeddings will fail unless mocked."
            )
        self.client = AsyncOpenAI(api_key=self.api_key)

        # Concurrency Control (Rate Limiting)
        # Default to 10 concurrent requests to avoid 429s on standard tier
        concurrency = int(os.getenv("MERIDIAN_EMBEDDING_CONCURRENCY", "10"))
        self._semaphore = asyncio.Semaphore(concurrency)

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Handle empty
        if not texts:
            return []

        # Batching logic: OpenAI has limits.
        # For MVP, we send all at once, relies on client to handle or user to not send massive lists.
        # We should implement simple batching here if the list is huge.
        # Let's batch by 2048 items (common safe limit).

        results = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                # Basic backoff wrapper
                response = await self._call_with_retry(batch)

                # Extract embeddings
                # response.data is list of objects with .embedding
                batch_embeddings = [item.embedding for item in response.data]
                results.extend(batch_embeddings)

            except Exception as e:
                logger.error("embedding_failed", error=str(e))
                raise e

        return results

    async def embed_query(self, text: str) -> List[float]:
        res = await self.embed_documents([text])
        return res[0]

    async def _call_with_retry(self, inputs: List[str], retries: int = 3) -> Any:
        """Simple exponential backoff."""
        for attempt in range(retries):
            try:
                # Replace newlines in text? Some models recommend it.
                # text-embedding-3-small is robust.
                return await self.client.embeddings.create(
                    input=inputs, model=self.model
                )
            except RateLimitError as e:
                wait = 2**attempt
                logger.warning(f"Rate limited. Waiting {wait}s. {e}")
                await asyncio.sleep(wait)
            except APIError as e:
                # 5xx errors might be transient
                # Use getattr to safely access status_code if present (it is in APIStatusError)
                code = getattr(e, "status_code", 500)
                if code >= 500:
                    wait = 2**attempt
                    logger.warning(f"OpenAI 5xx error. Waiting {wait}s. {e}")
                    await asyncio.sleep(wait)
                else:
                    raise e
        # Final attempt
        async with self._semaphore:
            return await self.client.embeddings.create(input=inputs, model=self.model)


class CohereEmbedding(EmbeddingProvider):
    def __init__(
        self, model: str = "embed-english-v3.0", api_key: Optional[str] = None
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("COHERE_API_KEY")
        if not self.api_key:
            logger.warning("COHERE_API_KEY not found.")

        # Delayed import to avoid hard dependency if not used
        import cohere

        self.client = cohere.AsyncClient(self.api_key)

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        # Cohere V3 models prefer input_type="search_document" for storage
        try:
            response = await self.client.embed(
                texts=texts, model=self.model, input_type="search_document"
            )
            return response.embeddings  # type: ignore[return-value]
        except Exception as e:
            logger.error("cohere_embedding_failed", error=str(e))
            raise e

    async def embed_query(self, text: str) -> List[float]:
        try:
            # Cohere V3 models prefer input_type="search_query" for retrieval
            response = await self.client.embed(
                texts=[text], model=self.model, input_type="search_query"
            )
            return response.embeddings[0]  # type: ignore[index]
        except Exception as e:
            logger.error("cohere_embedding_failed", error=str(e))
            raise e
