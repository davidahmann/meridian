from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
import tiktoken
import structlog

logger = structlog.get_logger()


@dataclass
class Index:
    name: str
    backend: str = "pgvector"
    chunk_size: int = 512
    overlap: float = 0.1
    description: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"  # Default

    def chunk_text(self, text: str) -> List[str]:
        """Chunks text using tiktoken."""
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            encoding = tiktoken.get_encoding("gpt2")  # Fallback

        tokens = encoding.encode(text)
        total_tokens = len(tokens)

        chunks = []
        step = int(self.chunk_size * (1 - self.overlap))

        if total_tokens <= self.chunk_size:
            return [text]

        for i in range(0, total_tokens, step):
            chunk_tokens = tokens[i : i + self.chunk_size]
            chunks.append(encoding.decode(chunk_tokens))

        return chunks


class IndexRegistry:
    def __init__(self) -> None:
        self.indexes: Dict[str, Index] = {}

    def register(self, index: Index) -> None:
        if index.name in self.indexes:
            logger.warning(f"Overwriting existing index: {index.name}")
        self.indexes[index.name] = index
        logger.info(f"Registered index: {index.name}")

    def get(self, name: str) -> Optional[Index]:
        return self.indexes.get(name)


def index(
    name: str,
    backend: str = "pgvector",
    chunk_size: int = 512,
    overlap: float = 0.1,
    embedding_model: str = "text-embedding-3-small",
) -> Callable[[Any], Any]:
    """
    Decorator to define a managed Index.
    Usage:
    @index(name="docs", chunk_size=512)
    def my_docs(): pass
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Create Index object
        idx = Index(
            name=name,
            backend=backend,
            chunk_size=chunk_size,
            overlap=overlap,
            description=func.__doc__,
            embedding_model=embedding_model,
        )

        # We need to register it.
        # Attach to function
        setattr(func, "_meridian_index", idx)

        # Return func as is
        return func

    return decorator
