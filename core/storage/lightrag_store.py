from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Callable

import numpy as np
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc

from config.settings import AppSettings
from core.llm.litellm_client import LiteLLMService


_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|\w+", re.UNICODE)


async def hash_embed(texts: list[str], embedding_dim: int = 384) -> np.ndarray:
    vectors: list[np.ndarray] = []
    for text in texts:
        vector = np.zeros(embedding_dim, dtype=np.float32)
        for token in _TOKEN_PATTERN.findall(text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:4], "big") % embedding_dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign * (1.0 + digest[5] / 255.0)
        norm = np.linalg.norm(vector)
        vectors.append(vector if norm == 0 else vector / norm)
    return np.stack(vectors, axis=0)


def build_rag_llm_func(
    settings: AppSettings,
    llm_service: LiteLLMService,
) -> Callable[..., Any]:
    async def rag_llm_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict[str, str]] | None = None,
        keyword_extraction: bool = False,
        **_: Any,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            content = system_prompt
            if keyword_extraction:
                content += "\n\n返回内容必须适合后续 JSON 解析。"
            messages.append({"role": "system", "content": content})
        elif keyword_extraction:
            messages.append(
                {
                    "role": "system",
                    "content": "你是一个信息抽取器，返回内容必须适合后续 JSON 解析。",
                }
            )
        if history_messages:
            messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})
        result = await llm_service.complete_text(
            model=settings.models.plot_model,
            messages=messages,
            temperature=0.1 if keyword_extraction else 0.3,
            max_tokens=settings.models.max_tokens,
            operation="lightrag_internal",
        )
        return result.text

    return rag_llm_func


class LightRAGStore:
    def __init__(self, settings: AppSettings, llm_service: LiteLLMService):
        self.settings = settings
        self.llm_service = llm_service
        self._rag: LightRAG | None = None
        self._initialized_dir: Path | None = None

    def _embedding_func(self) -> EmbeddingFunc:
        if self.settings.tuning.embedding_backend == "openai":
            from lightrag.llm.openai import openai_embed

            return EmbeddingFunc(
                embedding_dim=1536,
                func=openai_embed.func,
                max_token_size=8192,
                send_dimensions=True,
                model_name=self.settings.tuning.embedding_model,
            )
        return EmbeddingFunc(
            embedding_dim=self.settings.tuning.embedding_dim,
            func=hash_embed,
            max_token_size=8192,
            model_name="local-hash-v1",
        )

    def _session_rag_dir(self, session_name: str) -> Path:
        path = self.settings.lightrag_dir / session_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_client(self, session_name: str) -> LightRAG:
        session_dir = self._session_rag_dir(session_name)
        if self._rag is None or Path(self._rag.working_dir) != session_dir:
            self._rag = LightRAG(
                working_dir=str(session_dir),
                llm_model_func=build_rag_llm_func(self.settings, self.llm_service),
                llm_model_name=self.settings.models.lightrag_model_name,
                embedding_func=self._embedding_func(),
                chunk_token_size=self.settings.tuning.chunk_size,
                chunk_overlap_token_size=self.settings.tuning.chunk_overlap,
                top_k=self.settings.tuning.top_k,
                chunk_top_k=self.settings.tuning.chunk_top_k,
                auto_manage_storages_states=False,
            )
            self._initialized_dir = None
        return self._rag

    async def _get_ready_client(self, session_name: str) -> LightRAG:
        rag = self.get_client(session_name)
        working_dir = Path(rag.working_dir)
        if self._initialized_dir != working_dir:
            await rag.initialize_storages()
            self._initialized_dir = working_dir
        return rag

    async def index_text(self, session_name: str, chunks: list[str]) -> str:
        rag = await self._get_ready_client(session_name)
        return await rag.ainsert(chunks)

    async def append_text(self, session_name: str, text: str) -> str:
        rag = await self._get_ready_client(session_name)
        return await rag.ainsert(text)

    async def query_context(
        self,
        session_name: str,
        query: str,
        *,
        mode: str | None = None,
        response_type: str = "Bullet Points",
    ) -> str:
        rag = await self._get_ready_client(session_name)
        return await rag.aquery(
            query,
            param=QueryParam(
                mode=mode or self.settings.tuning.rag_query_mode,
                response_type=response_type,
                top_k=self.settings.tuning.top_k,
                chunk_top_k=self.settings.tuning.chunk_top_k,
                enable_rerank=False,
            ),
        )

    async def sample_passages(self, session_name: str, query: str) -> list[str]:
        context = await self.query_context(
            session_name,
            query,
            response_type="Bullet Points",
        )
        return [line.strip("- ").strip() for line in context.splitlines() if line.strip()]
