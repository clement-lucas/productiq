"""Product Strategist orchestrator + Concept Designer (Microsoft Agent Framework).

Flow for a product question:
  1. load user + project memory
  2. fan out IN PARALLEL to the Foundry specialist prompt agents (specialists.py)
  3. Concept Designer (AF agent) -> JSON: 3 options with 1–5 scores + rationale + citations,
     findings, PRD outline, open questions. Weighted totals are computed in scorecard.py.
  4. persist findings / options / scorecard version to project memory
  5. Product Strategist (AF agent) writes the user-facing markdown; numeric claims are checked
     against specialist outputs; an Adaptive Card is built.

All Agent Framework usage is isolated in `AgentRunner` so API changes stay local.
"""
from __future__ import annotations

import enum
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from . import cards, guardrails, telemetry
from .memory import Member, MemoryStore, NotAMemberError, ProjectMemory, utcnow
from .scorecard import CRITERIA, Scorecard, ScorecardError, load_weights, parse_options
from .specialists import SPECIALIST_AGENTS, SpecialistResult

PROMPTS = Path(__file__).parent / "prompts"


# ---------------------------------------------------------------------------- intents
class Intent(str, enum.Enum):
    ASK = "ask"
    SHOW_MEMORY = "show_memory"
    FORGET_ME = "forget_me"
    REMEMBER = "remember"
    RESCORE = "rescore"
    DECIDE = "decide"
    COLLAB = "collab"
    LINK_PROJECT = "link_project"
    NEW_PROJECT = "new_project"
    ADD_MEMBER = "add_member"
    HELP = "help"


_INTENT_RULES: list[tuple[Intent, re.Pattern[str]]] = [
    (Intent.SHOW_MEMORY, re.compile(r"^\s*(show|what is|what's)\s+(my\s+)?memory|^\s*私の(メモリ|記憶)を(表示|見せて)", re.I)),
    (Intent.FORGET_ME, re.compile(r"^\s*forget\s+me\b|^\s*(私の)?(記憶|メモリ)を(消して|削除)", re.I)),
    (Intent.REMEMBER, re.compile(r"^\s*remember\s+(that\s+)?(?P<fact>.+)", re.I)),
    (Intent.RESCORE, re.compile(r"re-?score\s+option\s+(?P<option>[A-Z])\b\s*(?P<instruction>.*)", re.I)),
    (Intent.DECIDE, re.compile(r"^\s*(we\s+)?(decide|choose|go with|pick)\s+option\s+(?P<option>[A-Z])\b(?P<reason>.*)", re.I)),
    (Intent.LINK_PROJECT, re.compile(r"^\s*link\s+(this\s+chat\s+to\s+)?project\s+(?P<project>prj-[\w-]+)", re.I)),
    (Intent.NEW_PROJECT, re.compile(r"^\s*new\s+project\s*:?\s*(?P<title>.+)", re.I)),
    (Intent.ADD_MEMBER, re.compile(r"^\s*add\s+(member\s+)?(?P<email>[\w.+-]+@[\w-]+\.[\w.-]+)(\s+as\s+(?P<role>.+))?", re.I)),
    (Intent.COLLAB, re.compile(r"(set\s*up|schedule|book|arrange)\s+(a\s+|the\s+)?(kickoff|meeting|sync)|"
                               r"(create|start)\s+(a\s+)?(group\s+)?chat|キックオフ|会議を(設定|調整)|ミーティングを(設定|調整)", re.I)),
    (Intent.HELP, re.compile(r"^\s*(help|\?|ヘルプ)\s*$", re.I)),
]


def classify(text: str) -> tuple[Intent, dict[str, str]]:
    for intent, pattern in _INTENT_RULES:
        m = pattern.search(text or "")
        if m:
            return intent, {k: (v or "").strip() for k, v in m.groupdict().items()}
    return Intent.ASK, {}


_SPECIALIST_KEYWORDS = {
    "voc": r"review|complain|feedback|customer|pet|tangl|voc|レビュー|不満|顧客|ペット",
    "market": r"market|demand|trend|competit|category|yoy|市場|需要|競合",
    "cost": r"cost|bom|price|supplier|sourc|motor|capacity|コスト|原価|サプライヤ|モーター",
    "logistics": r"logistic|ship|lead time|freight|plant|warehouse|物流|リードタイム|輸送",
    "future_tech": r"technolog|future|innovation|patent|battery|sensor|技術|特許|バッテリー",
}


def plan_specialists(question: str) -> list[str]:
    """Targeted questions hit matching specialists; broad/concept questions hit all five."""
    q = question.lower()
    if re.search(r"concept|option|idea|new product|innovat|propos|コンセプト|案|新製品", q):
        return list(SPECIALIST_AGENTS)
    hits = [k for k, pat in _SPECIALIST_KEYWORDS.items() if re.search(pat, q)]
    return hits or list(SPECIALIST_AGENTS)


def parse_json_block(text: str) -> dict[str, Any]:
    """Extract the first JSON object from model output (tolerates ```json fences / prose)."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


# ---------------------------------------------------------------------------- AF adapter
class Runner(Protocol):
    async def run(self, agent: str, prompt: str) -> str: ...


class AgentRunner:
    """Thin wrapper over Microsoft Agent Framework agents backed by Foundry models.

    TODO(verify): constructor kwargs of FoundryChatClient / Agent against the pinned
    agent-framework version (older builds: ChatAgent(chat_client=...) and
    agent_framework.azure.AzureAIAgentClient(project_endpoint=..., model_deployment_name=...)).
    """

    def __init__(self, settings: Any, credential: Any) -> None:
        self._settings = settings
        self._credential = credential
        self._agents: dict[str, Any] = {}
        self._specs = {
            "strategist": ("Product Strategist", "strategist.md", settings.model_reasoning_deployment),
            "designer": ("Concept Designer", "concept_designer.md", settings.model_reasoning_deployment),
        }

    def _build(self, key: str) -> Any:
        from agent_framework import Agent
        from agent_framework.foundry import FoundryChatClient

        name, prompt_file, deployment = self._specs[key]
        kwargs = {"project_endpoint": self._settings.foundry_project_endpoint, "credential": self._credential}
        try:
            client = FoundryChatClient(model=deployment, **kwargs)
        except TypeError:
            client = FoundryChatClient(model_deployment_name=deployment, **kwargs)
        instructions = (PROMPTS / prompt_file).read_text(encoding="utf-8")
        return Agent(client=client, name=name, instructions=instructions)

    async def run(self, agent: str, prompt: str) -> str:
        if agent not in self._agents:
            self._agents[agent] = self._build(agent)
        with telemetry.span(f"af.{agent}.run"):
            result = await self._agents[agent].run(prompt)
        return getattr(result, "text", None) or str(result)


# ---------------------------------------------------------------------------- orchestrator
@dataclass
class RequestContext:
    user_id: str
    user_name: str = ""
    channel: str = "web"  # web | teams
    chat_id: str | None = None
    conversation_type: str = "personal"  # personal | groupChat | channel
    project_id: str | None = None


@dataclass
class Reply:
    markdown: str
    card: dict[str, Any] | None = None
    project_id: str | None = None
    intent: Intent = Intent.ASK
    needs_collaboration: bool = False  # bot must obtain a Graph token and call CollaborationAgent.propose
    data: dict[str, Any] = field(default_factory=dict)


HELP_TEXT = (
    "Ask me a product question (e.g. *\"Propose three concepts for pet owners' vacuum complaints\"*).\n"
    "Commands: `re-score option C using the current motor platform`, `decide option C because …`, "
    "`set up a kickoff meeting`, `add ken@contoso.example as Design`, `link project prj-…`, "
    "`new project: <title>`, `remember that …`, `show my memory`, `forget me`."
)


class ProductStrategist:
    def __init__(self, store: MemoryStore, specialists: Any, runner: Runner,
                 weights: dict[str, float] | None = None, memory_hook: Any = None) -> None:
        self.store = store
        self.specialists = specialists
        self.runner = runner
        self.weights = weights or load_weights()
        self.memory_hook = memory_hook

    # -- entry point -----------------------------------------------------------------
    async def handle(self, ctx: RequestContext, text: str) -> Reply:
        intent, args = classify(text)
        lang = guardrails.detect_language(text)
        with telemetry.span("strategist.handle", intent=intent.value, channel=ctx.channel):
            if intent is Intent.HELP:
                return Reply(HELP_TEXT, intent=intent)
            if intent is Intent.SHOW_MEMORY:
                return await self._show_memory(ctx)
            if intent is Intent.FORGET_ME:
                n = await self.store.forget_user(ctx.user_id)
                await self.store.audit("none", "user.forget", ctx.user_id, {"deleted": n})
                return Reply(f"Done – I deleted {n} personal memory item(s). Shared project records were kept.",
                             intent=intent)
            if intent is Intent.REMEMBER:
                await self.store.remember(self.store.user_scope(ctx.user_id), args["fact"])
                if self.memory_hook is not None and self.memory_hook.enabled:
                    await self.memory_hook.remember(ctx.user_id, args["fact"])
                return Reply("Noted. Say `show my memory` to review or `forget me` to delete.", intent=intent)

            if intent is Intent.LINK_PROJECT and (not ctx.chat_id or ctx.conversation_type == "personal"):
                return Reply("`link project` works in a Teams group chat with ProductIQ added.", intent=intent)
            try:
                project = await self._resolve_project(ctx, text, intent, args)
            except NotAMemberError:
                return Reply("You're not a member of the ProductIQ project linked here, so I can't share it.",
                             intent=intent)
            except KeyError:
                return Reply("I couldn't find that project.", intent=intent)
            if project is None:
                return Reply("This chat isn't linked to a ProductIQ project yet. A project member can say "
                             "`link project <projectId>`.", intent=intent)

            if intent is Intent.LINK_PROJECT:
                await self.store.bind_chat(ctx.chat_id or "", project.projectId, ctx.user_id)
                return Reply(f"Linked this chat to **{project.title}**.", project_id=project.projectId,
                             intent=intent, card=cards.project_summary_card(project.to_item()))
            if intent is Intent.NEW_PROJECT:
                return Reply(f"Created project **{project.title}** (`{project.projectId}`). Ask your first question.",
                             project_id=project.projectId, intent=intent)
            if intent is Intent.ADD_MEMBER:
                project.add_member(Member(aadObjectId="", email=args["email"], role=args.get("role", "")))
                await self.store.save_project(project)
                return Reply(f"Added {args['email']} to **{project.title}** (identity resolved when the "
                             "kickoff is set up).", project_id=project.projectId, intent=intent)
            if intent is Intent.DECIDE:
                return await self._decide(ctx, project, args["option"].upper(), args.get("reason", ""))
            if intent is Intent.COLLAB:
                return Reply("Let me prepare the kickoff meeting and project chat for your approval…",
                             project_id=project.projectId, intent=intent, needs_collaboration=True)
            if intent is Intent.RESCORE:
                return await self.rescore(ctx, project, args["option"].upper(), args.get("instruction", ""), lang)
            return await self.answer(ctx, project, text, lang)

    # -- project resolution + membership -------------------------------------------------
    async def _resolve_project(self, ctx: RequestContext, text: str, intent: Intent,
                               args: dict[str, str]) -> ProjectMemory | None:
        me = Member(aadObjectId=ctx.user_id, name=ctx.user_name)
        if intent is Intent.LINK_PROJECT:
            return await self.store.get_project_for_member(args["project"], ctx.user_id)
        if intent is Intent.NEW_PROJECT:
            project = await self.store.create_project(args["title"], "", me)
        elif ctx.chat_id and ctx.conversation_type != "personal":
            return await self.store.resolve_chat_project(ctx.chat_id, ctx.user_id)
        elif ctx.project_id:
            project = await self.store.get_project_for_member(ctx.project_id, ctx.user_id)
        else:
            session = await self.store.get_session(ctx.user_id)
            if session.get("activeProjectId"):
                return await self.store.get_project_for_member(session["activeProjectId"], ctx.user_id)
            project = await self.store.create_project(text[:60], text, me)
        session = await self.store.get_session(ctx.user_id)
        session["activeProjectId"] = project.projectId
        await self.store.save_session(session)
        return project

    async def _show_memory(self, ctx: RequestContext) -> Reply:
        mem = await self.store.show_user_memory(ctx.user_id)
        lines = [f"- {m['text']} _(saved {m['at'][:10]})_" for m in mem["memories"]] or ["- (nothing saved)"]
        md = (f"**What ProductIQ remembers about you**\n\nActive project: `{mem['activeProjectId'] or '–'}`\n\n"
              + "\n".join(lines) + "\n\nSay `forget me` to delete your personal memory.")
        return Reply(md, intent=Intent.SHOW_MEMORY, data=mem)

    async def _decide(self, ctx: RequestContext, project: ProjectMemory, option: str, reason: str) -> Reply:
        text = f"Chose option {option}{(' – ' + reason.strip(' :-')) if reason.strip(' :-') else ''}"
        project.decisions.append({"text": text, "by": ctx.user_id, "at": utcnow()})
        await self.store.save_project(project)
        await self.store.add_decision(project.projectId, text, ctx.user_id)
        return Reply(f"Decision recorded: **{text}**.", project_id=project.projectId, intent=Intent.DECIDE)

    # -- main Q&A flow ------------------------------------------------------------------
    async def _gather(self, project: ProjectMemory, question: str, keys: list[str],
                      user_notes: list[str]) -> dict[str, SpecialistResult]:
        context = f"Project: {project.title}\nProblem: {project.problem}\n"
        if user_notes:
            context += "User preferences: " + "; ".join(user_notes[-5:]) + "\n"
        prompts = {k: f"{context}\nQuestion for you ({SPECIALIST_AGENTS[k]}): {question}\n"
                      "Return concise findings with figures and their sources." for k in keys}
        return await self.specialists.fan_out(prompts)

    @staticmethod
    def _evidence(results: dict[str, SpecialistResult]) -> tuple[str, list[str], list[str]]:
        """Sanitised evidence block for the LLMs + raw texts (numeric grounding) + citations."""
        blocks, raw, cites, flags = [], [], [], []
        for key, r in results.items():
            if not r.ok:
                blocks.append(f'<data source="{r.agent}">UNAVAILABLE ({r.error})</data>')
                continue
            s = guardrails.sanitize_retrieved(r.text, r.agent)
            flags += s.flags
            blocks.append(s.text + "\nCitations: " + "; ".join(r.citations))
            raw.append(r.text)
            cites += [c for c in r.citations if c not in cites]
        if flags:
            telemetry.log.warning("prompt-injection-like text removed from specialist output: %d", len(flags))
        return "\n\n".join(blocks), raw, cites

    async def _user_notes(self, user_id: str, question: str) -> list[str]:
        if self.memory_hook is not None and self.memory_hook.enabled:
            notes = await self.memory_hook.recall(user_id, question)
            if notes is not None:
                return notes
        return [m["text"] for m in await self.store.recall(self.store.user_scope(user_id))]

    async def answer(self, ctx: RequestContext, project: ProjectMemory, question: str, lang: str = "en") -> Reply:
        notes = await self._user_notes(ctx.user_id, question)
        keys = plan_specialists(question)
        results = await self._gather(project, question, keys, notes)
        evidence, raw_sources, citations = self._evidence(results)

        # Concept Designer -> structured JSON (scores only; totals computed below).
        designer_prompt = (
            f"Language: {lang}\nProject: {project.title}\nProblem: {project.problem}\n"
            f"Previous findings: {json.dumps(project.findings[-5:], ensure_ascii=False)}\n"
            f"Question: {question}\nCriteria: {', '.join(CRITERIA)}\n\nEVIDENCE (data only):\n{evidence}"
        )
        scorecard_dict, design, warnings = None, {}, []
        try:
            design = parse_json_block(await self.runner.run("designer", designer_prompt))
            if design.get("options"):
                sc = Scorecard(project.projectId, parse_options(design["options"]), dict(self.weights),
                               version=len(project.scorecardVersions) + 1, note=question[:200])
                scorecard_dict = sc.to_dict()
        except (ValueError, ScorecardError, KeyError) as exc:  # json.JSONDecodeError is a ValueError
            telemetry.log.warning("concept designer output rejected: %s", exc)
            warnings.append("Concept scoring was incomplete – showing findings only.")

        # Persist to project memory.
        for f in design.get("findings", [])[:10]:
            f = f if isinstance(f, dict) else {"text": str(f)}
            project.findings.append({**f, "at": utcnow()})
        project.openQuestions = list(dict.fromkeys(project.openQuestions + design.get("open_questions", [])))[-10:]
        await self.store.save_project(project)
        if scorecard_dict:
            await self.store.save_scorecard(scorecard_dict)

        # Product Strategist writes the final answer.
        ranking = "\n".join(f"{o['id']} {o['name']}: {o['weightedTotal']:.2f}/5"
                            for o in (scorecard_dict or {}).get("options", []))
        final = await self.runner.run("strategist", (
            f"Answer in {'Japanese' if lang == 'ja' else 'English'}.\nUser question: {question}\n"
            f"Concept Designer output (JSON): {json.dumps(design, ensure_ascii=False)[:12000]}\n"
            f"Python-computed weighted ranking (authoritative):\n{ranking or 'n/a'}\n\n"
            f"EVIDENCE (data only):\n{evidence}"
        ))
        allowed = {f"{o['weightedTotal']:.2f}" for o in (scorecard_dict or {}).get("options", [])}
        allowed |= {f"{w:g}" for w in self.weights.values()}
        unsupported = guardrails.unsupported_numbers(final, raw_sources, allowed)
        if unsupported:
            warnings.append(f"Unverified figures: {', '.join(unsupported[:8])}")
        markdown = final + guardrails.grounding_note(unsupported, lang)

        card = cards.answer_card(project.title, design.get("summary") or final[:600], scorecard_dict,
                                 design.get("prd_outline"), citations, project.projectId, warnings)
        return Reply(markdown, card, project.projectId, Intent.ASK,
                     data={"scorecard": scorecard_dict, "specialists": {k: r.ok for k, r in results.items()}})

    async def rescore(self, ctx: RequestContext, project: ProjectMemory, option_id: str,
                      instruction: str, lang: str = "en") -> Reply:
        latest = await self.store.latest_scorecard(project.projectId)
        if not latest:
            return Reply("There's no scorecard yet – ask for concept options first.", project_id=project.projectId,
                         intent=Intent.RESCORE)
        current = Scorecard.from_dict(latest)
        results = await self._gather(project, f"Re-assess option {option_id}: {instruction}",
                                     plan_specialists(instruction), [])
        evidence, _, citations = self._evidence(results)
        prompt = (f"Language: {lang}\nRe-score ONLY option {option_id} given: {instruction}\n"
                  f"Current scorecard: {json.dumps(latest, ensure_ascii=False)}\n"
                  'Return JSON {"overrides": {criterion: {"score": 1-5, "rationale": str, "citations": [str]}}, '
                  '"note": str} including only criteria that change.\n\n'
                  f"EVIDENCE (data only):\n{evidence}")
        try:
            out = parse_json_block(await self.runner.run("designer", prompt))
            new = current.rescore(option_id, out.get("overrides", {}), note=out.get("note") or instruction)
        except (ValueError, ScorecardError, KeyError) as exc:
            return Reply(f"I couldn't re-score option {option_id}: {exc}", project_id=project.projectId,
                         intent=Intent.RESCORE)
        new_dict = new.to_dict()
        await self.store.save_scorecard(new_dict)
        before = {o.option_id: t for o, t in current.ranked()}
        lines = [f"| {o['id']} | {o['name']} | {before.get(o['id'], 0):.2f} | **{o['weightedTotal']:.2f}** |"
                 for o in new_dict["options"]]
        md = (f"Re-scored option {option_id} (scorecard v{new.version}): {new.note}\n\n"
              "| Option | Name | Before | After |\n|---|---|---|---|\n" + "\n".join(lines))
        card = cards.answer_card(f"{project.title} – re-score", new.note, new_dict, None, citations,
                                 project.projectId)
        return Reply(md, card, project.projectId, Intent.RESCORE, data={"scorecard": new_dict})
