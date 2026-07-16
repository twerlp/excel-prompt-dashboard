#!/usr/bin/env python3
"""
Qdrant vector store for embedding-based retrieval.

Collections:
  stories      — user story + acceptance criteria embeddings
  frs_outputs   — generated functional requirement embeddings
  tc_outputs    — generated test case embeddings
  prompts       — prompt template embeddings

Usage:
  from qdrant_store import QdrantStore
  store = QdrantStore("./qdrant_data")
  store.ensure_collections()
  store.upsert_stories([...])
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer


class QdrantStore:
    """Manages Qdrant collections and provides high-level insert/query operations."""

    COLLECTIONS = {
        "stories":       "stories_v1",
        "frs_outputs":   "frs_outputs_v1",
        "tc_outputs":    "tc_outputs_v1",
        "prompts":       "prompts_v1",
    }

    def __init__(self, path: str = "./qdrant_data",
                 embedding_model: str = "all-MiniLM-L6-v2"):
        self.client = QdrantClient(path=path)
        self._embedder: Optional[SentenceTransformer] = None
        self._embedding_model_name = embedding_model

    @property
    def embedder(self) -> SentenceTransformer:
        if self._embedder is None:
            self._embedder = SentenceTransformer(self._embedding_model_name)
        return self._embedder

    # ── Collection management ──────────────────────────────────────────

    def ensure_collections(self) -> None:
        for coll_name in self.COLLECTIONS.values():
            if not self.client.collection_exists(coll_name):
                self.client.create_collection(
                    collection_name=coll_name,
                    vectors_config=models.VectorParams(
                        size=384, distance=models.Distance.COSINE
                    ),
                )

    def reset_collections(self) -> None:
        for coll_name in self.COLLECTIONS.values():
            if self.client.collection_exists(coll_name):
                self.client.delete_collection(coll_name)
        self.ensure_collections()

    # ── Embedding helpers ──────────────────────────────────────────────

    def embed(self, texts: List[str]) -> np.ndarray:
        return self.embedder.encode(texts, show_progress_bar=False)

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]

    # ── Stories ────────────────────────────────────────────────────────

    def upsert_stories(self, stories: List[Dict[str, Any]]) -> int:
        points = []
        for s in stories:
            text = s.get("story_text") or (
                s.get("user_story", "") + "\n" + s.get("acceptance_criteria", "")
            )
            vec = self.embed_one(text).tolist()
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, s["story_id"]))
            payload = {
                "story_id": s["story_id"],
                "title": s.get("title", ""),
                "domain": s.get("domain", ""),
                "priority": s.get("priority", ""),
                "story_points": s.get("story_points", 0),
                "sprint": s.get("sprint", ""),
                "status": s.get("status", ""),
                "dependencies": s.get("dependencies", ""),
                "user_story": s.get("user_story", ""),
                "acceptance_criteria": s.get("acceptance_criteria", ""),
            }
            points.append(models.PointStruct(
                id=point_id, vector=vec, payload=payload,
            ))
        self.client.upsert(
            collection_name=self.COLLECTIONS["stories"],
            points=points,
        )
        return len(points)

    def search_similar_stories(self, query_text: str, top_k: int = 3,
                                min_score: float = 0.0,
                                filter_domain: Optional[str] = None
                                ) -> List[Dict[str, Any]]:
        vec = self.embed_one(query_text).tolist()
        query_filter = None
        if filter_domain:
            query_filter = models.Filter(
                must=[models.FieldCondition(
                    key="domain", match=models.MatchValue(value=filter_domain)
                )],
            )
        results = self.client.query_points(
            collection_name=self.COLLECTIONS["stories"],
            query=vec,
            limit=top_k,
            query_filter=query_filter,
            score_threshold=min_score,
        ).points
        return [{"score": r.score, **(r.payload or {})} for r in results]

    def search_story_by_id(self, story_id: str) -> Optional[Dict[str, Any]]:
        results = self.client.scroll(
            collection_name=self.COLLECTIONS["stories"],
            scroll_filter=models.Filter(
                must=[models.FieldCondition(
                    key="story_id", match=models.MatchValue(value=story_id)
                )],
            ),
            limit=1,
        )[0]
        if results:
            return {**results[0].payload}
        return None

    # ── FRS Outputs ────────────────────────────────────────────────────

    def upsert_frs_output(self, experiment_id: str, story_id: str,
                          prompt_name: str, model: str, tier: int,
                          fr_lines: str, scores: Optional[Dict[str, float]] = None) -> None:
        vec = self.embed_one(fr_lines).tolist()
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, experiment_id))
        self.client.upsert(
            collection_name=self.COLLECTIONS["frs_outputs"],
            points=[models.PointStruct(
                id=point_id, vector=vec,
                payload={
                    "experiment_id": experiment_id,
                    "story_id": story_id,
                    "prompt_name": prompt_name,
                    "model": model,
                    "tier": tier,
                    "fr_text": fr_lines[:5000],
                    "scores_json": json.dumps(scores) if scores else "{}",
                },
            )],
        )

    def search_similar_frs(self, query_text: str, top_k: int = 3,
                            story_id: Optional[str] = None) -> List[Dict[str, Any]]:
        vec = self.embed_one(query_text).tolist()
        query_filter = None
        if story_id:
            query_filter = models.Filter(
                must=[models.FieldCondition(
                    key="story_id", match=models.MatchValue(value=story_id)
                )],
            )
        results = self.client.query_points(
            collection_name=self.COLLECTIONS["frs_outputs"],
            query=vec,
            limit=top_k,
            query_filter=query_filter,
        ).points
        return [{"score": r.score, **(r.payload or {})} for r in results]

    # ── TC Outputs ────────────────────────────────────────────────────

    def upsert_tc_output(self, experiment_id: str, story_id: str,
                         prompt_name: str, model: str, tier: int,
                         tc_text: str,
                         scores: Optional[Dict[str, float]] = None) -> None:
        vec = self.embed_one(tc_text).tolist()
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, experiment_id))
        self.client.upsert(
            collection_name=self.COLLECTIONS["tc_outputs"],
            points=[models.PointStruct(
                id=point_id, vector=vec,
                payload={
                    "experiment_id": experiment_id,
                    "story_id": story_id,
                    "prompt_name": prompt_name,
                    "model": model,
                    "tier": tier,
                    "tc_text": tc_text[:5000],
                    "scores_json": json.dumps(scores) if scores else "{}",
                },
            )],
        )

    def search_similar_tcs(self, query_text: str, top_k: int = 3,
                            story_id: Optional[str] = None) -> List[Dict[str, Any]]:
        vec = self.embed_one(query_text).tolist()
        query_filter = None
        if story_id:
            query_filter = models.Filter(
                must=[models.FieldCondition(
                    key="story_id", match=models.MatchValue(value=story_id)
                )],
            )
        results = self.client.query_points(
            collection_name=self.COLLECTIONS["tc_outputs"],
            query=vec,
            limit=top_k,
            query_filter=query_filter,
        ).points
        return [{"score": r.score, **(r.payload or {})} for r in results]

    # ── Prompts ────────────────────────────────────────────────────────

    def upsert_prompts(self, prompts: Dict[str, Dict[str, str]]) -> int:
        points = []
        for name, tmpl in prompts.items():
            text = (
                (tmpl.get("system_prompt", "") or "") + " " +
                (tmpl.get("user_prompt_template", "") or "")
            )[:2000]
            vec = self.embed_one(text).tolist()
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, name))
            points.append(models.PointStruct(
                id=point_id, vector=vec,
                payload={
                    "prompt_name": name,
                    "category": tmpl.get("category", ""),
                    "description": tmpl.get("description", ""),
                    "system_prompt": tmpl.get("system_prompt", ""),
                    "user_prompt_template": tmpl.get("user_prompt_template", ""),
                },
            ))
        self.client.upsert(
            collection_name=self.COLLECTIONS["prompts"],
            points=points,
        )
        return len(points)

    def search_similar_prompts(self, query_text: str, top_k: int = 3,
                                category: Optional[str] = None) -> List[Dict[str, Any]]:
        vec = self.embed_one(query_text).tolist()
        query_filter = None
        if category:
            query_filter = models.Filter(
                must=[models.FieldCondition(
                    key="category", match=models.MatchValue(value=category)
                )],
            )
        results = self.client.query_points(
            collection_name=self.COLLECTIONS["prompts"],
            query=vec,
            limit=top_k,
            query_filter=query_filter,
        ).points
        return [{"score": r.score, **(r.payload or {})} for r in results]
