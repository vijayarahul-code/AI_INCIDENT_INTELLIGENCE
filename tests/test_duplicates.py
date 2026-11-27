from duplicate_detection.trie import Trie
from duplicate_detection.similarity import find_potential_duplicates


def test_trie_insertion_and_search():
    trie = Trie()
    trie.insert("authentication token error", "INC-1001")
    trie.insert("payment timeout", "INC-1002")
    assert "INC-1001" in trie.search("authentication")
    assert "INC-1002" in trie.prefix_search("pay")


def test_similarity_detection():
    texts = [
        "Users cannot log in because authentication tokens expire early",
        "Users experience repeated login failures due to expired tokens",
        "Database connection pool is saturated",
    ]
    results = find_potential_duplicates(texts, threshold=0.30)
    assert len(results) >= 1


def test_trie_exact_search_does_not_return_prefix_matches():
    trie = Trie()
    trie.insert("login", "INC001")
    trie.insert("login issue", "INC002")
    trie.insert("login", "INC001")

    assert trie.search("login") == ["INC001", "INC002"]
    assert trie.search("login issue") == ["INC002"]
    assert trie.search("log") == []
    assert trie.prefix_search("log") == ["INC001", "INC002"]


def test_prompt_incidents_find_login_matches_without_unrelated_candidates():
    incidents = [
        "Login button is not responding.",
        "Unable to click the login button.",
        "Payment gateway is unavailable.",
        "The login functionality is not working.",
        "Server is completely unavailable.",
    ]

    results = find_potential_duplicates(incidents, threshold=0.35)
    pairs = {(left, right) for left, right, _ in results}

    assert (0, 1) in pairs
    assert (0, 3) in pairs or (1, 3) in pairs
    assert all(not ({left, right} & {0, 1, 3} and {left, right} & {2, 4}) for left, right in pairs)
    assert all(left != right and 0.0 <= score <= 1.0 for left, right, score in results)
