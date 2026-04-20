from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .common import RagInteraction, RagPaths, default_session_id, slugify, utc_now
from .evaluation import RagEvalSample, aggregate_scores, publish_rag_observability
from .llm import LMStudioClient
from .memory import MemoryManager
from .vectorstore import query_collection


class RagState(TypedDict, total=False):
    session_id: str
    interaction_id: str
    question: str
    collection_name: str
    security_collection: str
    retrieved_docs: list[dict[str, Any]]
    memory_context: str
    external_memory_context: str
    answer: str
    citations: list[dict[str, Any]]
    model_name: str
    expected_output: str
    task_type: str
    remember: bool
    persist_interaction: bool
    usage: dict[str, Any]
    latency_seconds: float
    evaluation: dict[str, Any]
    fallback_text: str
    provider_id: str


class RagWorkflow:
    def __init__(
        self,
        paths: RagPaths,
        *,
        top_k: int = 4,
        default_collection: str = "knowledge_base",
        security_collection: str = "security_base",
        mock_llm: bool = False,
        provider_id: str | None = None,
    ) -> None:
        self.paths = paths
        self.paths.ensure()
        self.top_k = top_k
        self.default_collection = default_collection
        self.security_collection = security_collection
        self.provider_id = provider_id
        self.memory = MemoryManager(paths)
        self.llm = LMStudioClient(mock=mock_llm, provider_id=provider_id)
        self.graph = self._compile_graph()

    def _compile_graph(self):
        builder = StateGraph(RagState)
        builder.add_node("load_memory", self._load_memory)
        builder.add_node("retrieve", self._retrieve)
        builder.add_node("generate", self._generate)
        builder.add_node("evaluate", self._evaluate)
        builder.add_node("persist", self._persist)
        builder.add_edge(START, "load_memory")
        builder.add_edge("load_memory", "retrieve")
        builder.add_edge("retrieve", "generate")
        builder.add_edge("generate", "evaluate")
        builder.add_edge("evaluate", "persist")
        builder.add_edge("persist", END)
        return builder.compile()

    def _load_memory(self, state: RagState) -> RagState:
        session_id = state.get("session_id") or default_session_id()
        memory_parts = [
            self.memory.build_memory_context(session_id),
            state.get("external_memory_context", ""),
        ]
        return {
            "session_id": session_id,
            "interaction_id": state.get("interaction_id") or f"rag-{slugify(utc_now())}",
            "memory_context": "\n\n".join(part for part in memory_parts if part).strip(),
        }

    def _safe_query_collection(self, collection_name: str, question: str, *, top_k: int) -> list[Any]:
        try:
            return query_collection(self.paths, collection_name, question, top_k=top_k)
        except Exception:
            return []

    def _retrieve(self, state: RagState) -> RagState:
        question = state["question"]
        collection_name = state.get("collection_name") or self.default_collection
        security_collection = state.get("security_collection") or self.security_collection
        retrieved = self._safe_query_collection(collection_name, question, top_k=self.top_k)
        security_hits = self._safe_query_collection(security_collection, question, top_k=2)
        try:
            memory_hits = self.memory.retrieve_memory_facts(question, top_k=2)
        except Exception:
            memory_hits = []

        merged: list[dict[str, Any]] = []
        for item in retrieved:
            merged.append({"chunk_id": item.chunk_id, "text": item.text, "metadata": item.metadata, "distance": item.distance, "channel": "knowledge"})
        for item in security_hits:
            merged.append({"chunk_id": item.chunk_id, "text": item.text, "metadata": item.metadata, "distance": item.distance, "channel": "security"})
        for item in memory_hits:
            merged.append({**item, "channel": "memory"})

        fallback = "\n\n".join(item["text"] for item in merged[:2]).strip()
        return {
            "collection_name": collection_name,
            "security_collection": security_collection,
            "retrieved_docs": merged,
            "citations": [
                {
                    "chunk_id": item["chunk_id"],
                    "channel": item["channel"],
                    "source": item["metadata"].get("source_path") or item["metadata"].get("source_url") or item["metadata"].get("source"),
                    "title": item["metadata"].get("title") or item["metadata"].get("rule_id") or item["metadata"].get("document_id"),
                }
                for item in merged
            ],
            "fallback_text": fallback,
        }

    def _generate(self, state: RagState) -> RagState:
        retrieved_context = "\n\n".join(
            f"[{item['channel'].upper()}] {item['text']}" for item in state.get("retrieved_docs", [])
        ).strip()
        memory_context = state.get("memory_context", "")
        system_prompt = (
            "Voce e um assistente local para shell, scripts, git, docker, tmux e programacao. "
            "Responda de forma operacional, segura e objetiva. "
            "Se houver regras de seguranca no contexto, elas tem prioridade. "
            "Nao invente comandos destrutivos nem passos sem suporte no contexto."
        )
        user_prompt = "\n\n".join(
            part
            for part in (
                f"Memoria:\n{memory_context}" if memory_context else "",
                f"Contexto recuperado:\n{retrieved_context}" if retrieved_context else "",
                f"Pergunta:\n{state['question']}",
            )
            if part
        )
        provider_id = state.get("provider_id") or self.provider_id
        llm = self.llm if provider_id == self.provider_id else LMStudioClient(mock=self.llm.mock, provider_id=provider_id)
        response = llm.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model_name=state.get("model_name"),
            fallback_text=state.get("fallback_text", ""),
        )
        return {
            "answer": response.content,
            "model_name": response.model_name,
            "provider_id": response.provider_id,
            "usage": response.usage,
            "latency_seconds": response.latency_seconds,
        }

    def _evaluate(self, state: RagState) -> RagState:
        expected = state.get("expected_output", "")
        if not expected:
            return {"evaluation": {}}
        context = "\n\n".join(item["text"] for item in state.get("retrieved_docs", []))
        sample = RagEvalSample(
            sample_id=state["interaction_id"],
            task_type=state.get("task_type", "generic"),
            question=state["question"],
            answer=state.get("answer", ""),
            expected_output=expected,
            context=context,
            latency_seconds=float(state.get("latency_seconds", 0.0)),
            prompt_tokens=int(state.get("usage", {}).get("prompt_tokens", 0)),
            completion_tokens=int(state.get("usage", {}).get("completion_tokens", 0)),
            total_tokens=int(state.get("usage", {}).get("total_tokens", 0)),
        )
        return {"evaluation": aggregate_scores([sample])}

    def _persist(self, state: RagState) -> RagState:
        if not state.get("persist_interaction", True):
            return {}
        interaction = RagInteraction(
            interaction_id=state["interaction_id"],
            session_id=state["session_id"],
            collection_name=state["collection_name"],
            question=state["question"],
            answer=state.get("answer", ""),
            citations=state.get("citations", []),
            model_name=state.get("model_name", ""),
            created_at=utc_now(),
            expected_output=state.get("expected_output"),
            task_type=state.get("task_type", "generic"),
            usage=state.get("usage", {}),
            evaluation=state.get("evaluation", {}),
        )
        self.memory.record_interaction(interaction.session_id, interaction.to_dict())
        if state.get("remember"):
            self.memory.promote_fact(
                interaction.session_id,
                interaction.answer,
                source=interaction.interaction_id,
                metadata={"question": interaction.question, "collection_name": interaction.collection_name},
            )
        return {}

    def invoke(
        self,
        *,
        question: str,
        session_id: str | None = None,
        collection_name: str | None = None,
        model_name: str | None = None,
        provider_id: str | None = None,
        expected_output: str | None = None,
        task_type: str = "generic",
        remember: bool = False,
        external_memory_context: str = "",
        persist_interaction: bool = True,
        publish_observability: bool = True,
    ) -> dict[str, Any]:
        state: RagState = {
            "question": question,
            "session_id": session_id or default_session_id(),
            "collection_name": collection_name or self.default_collection,
            "model_name": model_name,
            "provider_id": provider_id or self.provider_id,
            "expected_output": expected_output or "",
            "task_type": task_type,
            "remember": remember,
            "external_memory_context": external_memory_context,
            "persist_interaction": persist_interaction,
        }
        result = self.graph.invoke(state)
        if publish_observability and expected_output:
            context = "\n\n".join(item["text"] for item in result.get("retrieved_docs", []))
            sample = RagEvalSample(
                sample_id=str(result.get("interaction_id", f"rag-{slugify(utc_now())}")),
                task_type=task_type,
                question=question,
                answer=str(result.get("answer", "")),
                expected_output=expected_output,
                context=context,
                latency_seconds=float(result.get("latency_seconds", 0.0)),
                prompt_tokens=int(result.get("usage", {}).get("prompt_tokens", 0)),
                completion_tokens=int(result.get("usage", {}).get("completion_tokens", 0)),
                total_tokens=int(result.get("usage", {}).get("total_tokens", 0)),
            )
            observability_report_id = f"rag-query-{slugify(result.get('interaction_id', utc_now()))}"
            langfuse_status, phoenix_status = publish_rag_observability(
                paths=self.paths,
                report_id=observability_report_id,
                model_name=str(result.get("model_name", "")),
                samples=[sample],
            )
            result["langfuse"] = langfuse_status
            result["phoenix"] = phoenix_status
        return result
