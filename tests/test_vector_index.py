from src.services.vector_index import VectorIndexClient


def test_faiss_bulk_upsert_and_query():
    client = VectorIndexClient(backend="faiss")
    # three orthogonal/diagonal vectors
    client.bulk_upsert([
        ("a", [1.0, 0.0]),
        ("b", [0.0, 1.0]),
        ("c", [1.0, 1.0]),
    ])

    res = client.query([1.0, 1.0], k=3)
    ids = [r[0] for r in res]

    # most similar to [1,1] should be 'c'
    assert ids[0] == "c"
    # we expect all three ids to be returned when k=3
    assert set(ids) == {"a", "b", "c"}


def test_faiss_upsert_single():
    client = VectorIndexClient(backend="faiss")
    client.upsert("x", [0.0, 1.0])
    res = client.query([0.0, 1.0], k=1)
    assert len(res) == 1
    assert res[0][0] == "x"
