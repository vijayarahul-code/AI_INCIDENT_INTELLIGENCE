from __future__ import annotations

import re
from typing import Dict, List, Set


class TrieNode:
    def __init__(self):
        self.children: Dict[str, "TrieNode"] = {}
        self.is_end_of_word = False
        self.incident_ids: Set[str] = set()


class Trie:
    def __init__(self):
        self.root = TrieNode()

    @staticmethod
    def _tokens(keyword: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", keyword.lower())

    def _insert_tokens(self, normalized_tokens: List[str], incident_id: str) -> None:
        for token in normalized_tokens:
            node = self.root
            for char in token.lower():
                node = node.children.setdefault(char, TrieNode())
            node.is_end_of_word = True
            node.incident_ids.add(incident_id)

    def insert(self, keyword: str, incident_id: str) -> None:
        tokens = self._tokens(keyword)
        if not tokens:
            return
        self._insert_tokens(tokens, incident_id)
        phrase = " ".join(tokens)
        node = self.root
        for char in phrase:
            node = node.children.setdefault(char, TrieNode())
        node.is_end_of_word = True
        node.incident_ids.add(incident_id)

    def _find_node(self, text: str) -> TrieNode | None:
        node = self.root
        for char in text:
            if char not in node.children:
                return None
            node = node.children[char]
        return node

    def _collect_matches(self, prefix: str) -> List[str]:
        node = self._find_node(prefix)
        if node is None:
            return []
        results: List[str] = []

        def dfs(current: TrieNode) -> None:
            if current.is_end_of_word:
                results.extend(sorted(current.incident_ids))
            for child in current.children.values():
                dfs(child)

        dfs(node)
        return sorted(set(results))

    def search(self, keyword: str) -> List[str]:
        tokens = self._tokens(keyword)
        if not tokens:
            return []
        node = self._find_node(" ".join(tokens))
        if node is None or not node.is_end_of_word:
            return []
        return sorted(node.incident_ids)

    def prefix_search(self, prefix: str) -> List[str]:
        tokens = self._tokens(prefix)
        if not tokens:
            return []
        results = set()
        for token in tokens:
            results.update(self._collect_matches(token))
        return sorted(results)
