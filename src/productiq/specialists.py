"""Calls the Foundry prompt agents (CONTRACT.md) via the Responses API + agent_reference.

Everything Foundry-SDK-specific lives here so preview API changes stay contained.
"""
from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from typing import Any

from . import telemetry

# key -> Foundry prompt agent name (scripts/foundry/create_agents.py creates these).
SPECIALIST_AGENTS: dict[str, str] = {
    "voc": "productiq-voc-analyst",
    "market": "productiq-market-scout",
    "cost": "productiq-cost-supplier",
    "logistics": "productiq-logistics",
    "future_tech": "productiq-future-tech",
}
SPECIALIST_SOURCES = {  # default provenance label when the agent returns no url annotations
    "voc": "Fabric IQ – fact_feedback (synthetic)",
    "market": "Bing grounding / Foundry IQ knowledge base",
    "cost": "Fabric IQ – fact_bom_cost, fact_supplier_capacity (synthetic)",
    "logistics": "Fabric IQ – fact_logistics (synthetic)",
    "future_tech": "Bing grounding / Foundry IQ knowledge base",
}
# TODO(verify): early azure-ai-projects 2.x previews used extra_body={"agent": {...}};
# current docs use "agent_reference". Change this one constant if the service rejects it.
AGENT_REF_KEY = "agent_reference"
TIMEOUT_S = 90


@dataclass
class SpecialistResult:
    key: str
    agent: str
    text: str = ""
    citations: list[str] = field(default_factory=list)
    ok: bool = True
    error: str = ""
    latency_ms: int = 0


def _extract_citations(response: Any, key: str) -> list[str]:
    cites: list[str] = []
    for item in getattr(response, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            for ann in getattr(part, "annotations", None) or []:
                url = getattr(ann, "url", None)
                title = getattr(ann, "title", None) or url
                if url and f"{title} – {url}" not in cites:
                    cites.append(f"{title} – {url}")
    return cites or [SPECIALIST_SOURCES.get(key, key)]


class SpecialistClient:
    def __init__(self, project_endpoint: str, credential: Any) -> None:
        self._endpoint = project_endpoint
        self._credential = credential
        self._openai: Any = None
        self._lock = asyncio.Lock()

    async def _client(self) -> Any:
        async with self._lock:
            if self._openai is None:
                from azure.ai.projects.aio import AIProjectClient  # lazy import

                project = AIProjectClient(endpoint=self._endpoint, credential=self._credential)
                client = project.get_openai_client()
                # TODO(verify): sync in azure-ai-projects>=2.x, awaitable in some 1.x previews.
                self._openai = await client if inspect.isawaitable(client) else client
            return self._openai

    async def ask(self, key: str, prompt: str) -> SpecialistResult:
        agent = SPECIALIST_AGENTS[key]
        started = time.perf_counter()
        with telemetry.span("specialist.call", agent=agent) as s:
            try:
                client = await self._client()
                resp = await asyncio.wait_for(
                    client.responses.create(
                        input=prompt,
                        extra_body={AGENT_REF_KEY: {"name": agent, "type": "agent_reference"}},
                    ),
                    timeout=TIMEOUT_S,
                )
                result = SpecialistResult(key, agent, getattr(resp, "output_text", "") or "",
                                          _extract_citations(resp, key))
            except Exception as exc:  # one failing specialist must not sink the whole answer
                telemetry.log.warning("specialist %s failed: %s", agent, exc)
                result = SpecialistResult(key, agent, ok=False, error=type(exc).__name__)
            result.latency_ms = int((time.perf_counter() - started) * 1000)
            if s is not None:
                s.set_attribute("productiq.ok", result.ok)
                s.set_attribute("productiq.latency_ms", result.latency_ms)
        return result

    async def fan_out(self, prompts: dict[str, str]) -> dict[str, SpecialistResult]:
        """Call several specialists in parallel. `prompts` maps specialist key -> prompt."""
        results = await asyncio.gather(*(self.ask(k, p) for k, p in prompts.items()))
        return {r.key: r for r in results}
