---
title: "RAG Without LangChain: Building Retrieval Pipelines in Plain Python"
description: "How to build production RAG applications without LangChain's complexity. Using Python decorators for vector search, context assembly, and token budgets."
keywords: rag without langchain, langchain alternative, simple rag pipeline, python rag, vector search python, retrieval augmented generation
date: 2025-01-13
---

# RAG Without LangChain

LangChain promised to simplify LLM development. Instead, it gave us:

- 47 different chain types
- Nested abstractions you can't debug
- Breaking changes every minor version
- Documentation that doesn't match the code

You don't need LangChain to build RAG. You need three things:

1. **Vector search** — find relevant documents
2. **Context assembly** — fit them in the token budget
3. **LLM call** — get the response

That's it. Let's build it.

## The LangChain Way

```python
from langchain.chains import RetrievalQA
from langchain.vectorstores import Pinecone
from langchain.embeddings import OpenAIEmbeddings
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory

# 50 more lines of configuration...
chain = RetrievalQA.from_chain_type(
    llm=OpenAI(),
    chain_type="stuff",
    retriever=vectorstore.as_retriever(),
    memory=memory,
    chain_type_kwargs={"prompt": prompt}
)

result = chain.run(query)
```

When this breaks (and it will), good luck debugging nested chain abstractions.

## The Fabra Way

```python
from fabra.core import FeatureStore
from fabra.retrieval import retriever
from fabra.context import context, ContextItem
import openai

store = FeatureStore()

# 1. Vector Search
@retriever(index="docs", top_k=5)
async def search_docs(query: str):
    pass  # Auto-wired to pgvector

# 2. Context Assembly
@context(store, max_tokens=4000)
async def build_context(user_id: str, query: str):
    docs = await search_docs(query)
    tier = await store.get_feature("user_tier", user_id)

    return [
        ContextItem(
            content="You are a helpful assistant.",
            priority=0,
            required=True
        ),
        ContextItem(
            content=f"User tier: {tier}",
            priority=1
        ),
        ContextItem(
            content=f"Relevant docs:\n{docs}",
            priority=2
        ),
    ]

# 3. LLM Call (just use the OpenAI SDK directly)
async def chat(user_id: str, query: str):
    ctx = await build_context(user_id, query)

    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": ctx.content},
            {"role": "user", "content": query}
        ]
    )
    return response.choices[0].message.content
```

No chains. No abstractions. Just Python functions you can read and debug.

## Vector Search Without Pinecone

Pinecone is $70/month minimum. pgvector is free and runs in Postgres.

Fabra uses pgvector for vector search:

```python
# Index documents
await store.index("docs", "doc_1", "Fabra is a feature store...")
await store.index("docs", "doc_2", "Features are defined with decorators...")

# Search (automatic embedding via OpenAI)
@retriever(index="docs", top_k=5)
async def search_docs(query: str):
    pass  # Returns list of matching documents
```

The `@retriever` decorator auto-wires to your index. No configuration needed.

For local development, embeddings are cached. For production, pgvector handles the similarity search.

## Token Budgets That Actually Work

LangChain's "stuff" chain type just concatenates documents until they don't fit. Then it fails.

Fabra's `@context` decorator handles this properly:

```python
@context(store, max_tokens=4000)
async def build_context(query: str):
    docs = await search_docs(query)  # Might return 10 docs

    return [
        ContextItem(content="System prompt", priority=0, required=True),
        ContextItem(content=docs[0], priority=1),
        ContextItem(content=docs[1], priority=2),
        ContextItem(content=docs[2], priority=3),
        # ... more docs with lower priority
    ]
```

If the total exceeds 4000 tokens:

1. Required items are always included
2. Optional items are dropped by priority (highest number first)
3. You never get a "context too long" error

The assembled `Context` object tells you exactly what was included and dropped:

```python
ctx = await build_context("test query")
print(ctx.meta["token_usage"])  # 3847
print(ctx.meta["items_included"])  # 5
print(ctx.meta["items_dropped"])  # 2
```

## User Personalization + RAG

This is where Fabra shines. LangChain treats RAG and user features as separate concerns. Fabra unifies them:

```python
@feature(entity=User, refresh="daily")
def user_tier(user_id: str) -> str:
    return lookup_tier(user_id)

@feature(entity=User, refresh="1h")
def recent_topics(user_id: str) -> list:
    return get_user_interests(user_id)

@context(store, max_tokens=4000)
async def personalized_context(user_id: str, query: str):
    tier = await store.get_feature("user_tier", user_id)
    topics = await store.get_feature("recent_topics", user_id)

    # Boost docs matching user interests
    docs = await search_docs(query, boost_topics=topics)

    return [
        ContextItem(content=f"User is {tier} tier", priority=0),
        ContextItem(content=f"User interests: {topics}", priority=1),
        ContextItem(content=str(docs), priority=2),
    ]
```

Features and retrieval in the same system. No glue code.

## Debugging Is Just Debugging

When something goes wrong in LangChain:

```
langchain.exceptions.OutputParserException:
  Could not parse LLM output: ...
```

Good luck tracing that through 5 layers of chain abstractions.

When something goes wrong in Fabra:

```python
# It's just Python. Add a print statement.
@context(store, max_tokens=4000)
async def build_context(query: str):
    docs = await search_docs(query)
    print(f"Found {len(docs)} docs")  # This works
    print(f"First doc: {docs[0]}")    # So does this
    ...
```

## Try It

```bash
pip install "fabra[ui]"
```

```python
from fabra.core import FeatureStore
from fabra.retrieval import retriever
from fabra.context import context, ContextItem

store = FeatureStore()

@retriever(index="docs", top_k=3)
async def search(query: str):
    pass

@context(store, max_tokens=2000)
async def build(query: str):
    docs = await search(query)
    return [ContextItem(content=str(docs), priority=0)]

# Index some docs
await store.index("docs", "1", "Your content here")

# Build context
ctx = await build("search query")
print(ctx.content)
```

No chains. No abstractions. Just Python.

[Full RAG tutorial →](../use-cases/rag-chatbot.md)
