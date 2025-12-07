from meridian.index import Index


def test_chunking_basic() -> None:
    # chunk_size is tokens, roughly 4 chars per token.
    # We use a small chunk size for testing.
    idx = Index(name="test", chunk_size=5, overlap=0)

    text = "Hello world this is a test"
    # Tokens (approx): [Hello, world, this, is, a, test] -> 6 tokens
    # If chunk_size=5, we expect 2 chunks: [Hello...a] and [test]

    chunks = idx.chunk_text(text)
    assert len(chunks) >= 2
    assert "Hello" in chunks[0]
    assert "test" in chunks[1]


def test_chunking_overlap() -> None:
    idx = Index(name="overlap", chunk_size=4, overlap=0.5)
    # step = 2
    text = "one two three four five six"
    # Tokens: [one, two, three, four, five, six]
    # Chunks:
    # 0..4: one two three four
    # 2..6: three four five six

    chunks = idx.chunk_text(text)
    # Depending on exact tokenization:
    assert len(chunks) >= 2
    # Verify overlap
    chunk1 = chunks[0]
    chunk2 = chunks[1]

    # "three" and "four" should likely be in both
    common = set(chunk1.split()) & set(chunk2.split())
    assert len(common) > 0
