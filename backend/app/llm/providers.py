"""LLM + embedding providers behind one small interface.

OpenAIProvider   gpt-4o-mini (JSON mode) + text-embedding-3-small over plain REST.
                 The key stays on the server and is sent only in the Authorization header.
OfflineProvider  no network: regex + keyword rules + hashed bag-of-words vectors.
                 Runs the demo with no key or no Wi-Fi, and makes tests deterministic.

Both expose the same two methods (the strategy pattern):
    generate(prompt, json_mode=False) -> LLMReply(text, model, prompt_tokens, completion_tokens)
    embed(texts)                      -> list[np.ndarray]   (unit length, so dot = cosine)

The caller (analysis.py) parses and validates the JSON itself, so the trace can show
the raw reply even when it is broken.
"""
import hashlib
import json
import re
from dataclasses import dataclass

import numpy as np
import requests

from ..config import settings
from ..departments import KEYWORDS, keyword_scores

OPENAI_BASE = "https://api.openai.com/v1"
DECISIONS_MODEL = "gpt-6-luna"
OFFLINE_DIM = 768


class LLMError(RuntimeError):
    pass


@dataclass
class LLMReply:
    text: str
    model: str
    prompt_tokens: int | None = None       # None when the provider doesn't report usage
    completion_tokens: int | None = None


def normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    return vec if norm == 0 else vec / norm


# ---------------------------------------------------------------- OpenAI

class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, embed_model: str):
        self.api_key, self.model, self.embed_model = api_key, model, embed_model
        self.last_embed_tokens = 0          # read by the trace for the cost estimate

    def _post(self, path: str, body: dict) -> dict:
        try:
            resp = requests.post(f"{OPENAI_BASE}{path}", json=body, timeout=60,
                                 headers={"Authorization": f"Bearer {self.api_key}"})
        except requests.RequestException as exc:
            raise LLMError(f"OpenAI unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise LLMError(f"OpenAI {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def generate(self, prompt: str, json_mode: bool = False) -> LLMReply:
        body = {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
        if self.model.startswith("gpt-4"):
            body["temperature"] = 0.1                 # older models: low randomness
        else:
            body["reasoning_effort"] = "low"          # gpt-6 family: fixed temperature, keep thinking cheap
        if json_mode:
            body["response_format"] = {"type": "json_object"}   # reply is guaranteed to parse
        data = self._post("/chat/completions", body)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected OpenAI response: {str(data)[:300]}") from exc
        usage = data.get("usage", {})
        return LLMReply(text.strip(), data.get("model", self.model),
                        usage.get("prompt_tokens"), usage.get("completion_tokens"))

    def decide(self, text: str, questions: list[dict]) -> dict:
        """OpenAI Decisions API: typed answers with real probabilities (choice / score / predicate).
        Only gpt-6-luna is supported there. Input costs $0.10 per 1M tokens; output tokens are free."""
        return self._post("/decisions", {"model": DECISIONS_MODEL, "input": text, "questions": questions})

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        vectors = []
        for start in range(0, len(texts), 100):
            data = self._post("/embeddings", {"model": self.embed_model,
                                              "input": texts[start:start + 100]})
            vectors += [normalize(np.array(d["embedding"], dtype=np.float32)) for d in data["data"]]
            self.last_embed_tokens += data.get("usage", {}).get("total_tokens", 0)
        return vectors


# ---------------------------------------------------------------- Offline

DEPARTMENT_KEYWORDS = KEYWORDS          # from departments.py, shared with the prompt and the UI
DOC_TYPES = [("invoice", "Invoice"), ("circular", "Circular"), ("tender", "Tender Notice"),
             ("amendment", "Contract Amendment"), ("report", "Report"), ("notice", "Notice"),
             ("letter", "Letter")]
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_RE = re.compile(rf"\b\d{{1,2}} (?:{MONTHS}) \d{{4}}\b")
AMOUNT_RE = re.compile(r"(?:Rs\.?|₹|INR)\s?\d(?:[\d,]*\d)?(?:\.\d+)?(?:\s?(?:crore|lakh))?")
REF_ID_RE = re.compile(r"\b[A-Z]{2,}(?:[/-][A-Z0-9.]+)+\b")
VENDOR_RE = re.compile(r"(?:M/s\.?\s+)?((?:[A-Z][\w&.]*\s+){1,5}(?:Pvt\.?\s+Ltd|Private Limited|Ltd|Limited))")
ACTION_RE = re.compile(r"\b(shall|must|required to|should|submit|ensure|to (?:test|replace|run|attend|log|carry out))\b", re.I)
DUE_RE = re.compile(rf"\b(?:by|before|until|on or before)\s+(\d{{1,2}} (?:{MONTHS}) \d{{4}})")
SENTENCE_RE = re.compile(r"(?<!Rs\.)(?<!No\.)(?<=[.!?])\s+|\n+")
QUESTION_WORDS = {w[:5] for w in ("what", "which", "when", "where", "who", "how", "the", "and",
                  "for", "are", "was", "does", "did", "any", "many", "much", "there", "our",
                  "with", "from", "must", "has", "been", "need", "their")}


def stems(text: str) -> set[str]:
    """Crude stemming: first 5 letters, so 'register' matches 'registration'."""
    return {w[:5] for w in re.findall(r"[a-z0-9]{3,}", text.lower())}


def sentences(text: str) -> list[str]:
    return [" ".join(s.split()) for s in SENTENCE_RE.split(text) if len(s.split()) > 3]


class OfflineProvider:
    """Deterministic stand-in for the LLM. Simple on purpose: easy to explain."""
    name = "offline"
    model = "offline-rules-v1"
    embed_model = "offline-hashing"
    last_embed_tokens = 0

    def generate(self, prompt: str, json_mode: bool = False) -> LLMReply:
        if prompt.startswith("LEVEL 1"):
            out = json.dumps(self._level1(prompt.split("DOCUMENT:", 1)[-1]))
        elif prompt.startswith("LEVEL 2"):
            out = json.dumps(self._level2(prompt))
        elif prompt.startswith("HYPOTHETICAL DOCUMENT"):
            # HyDE needs a generative model; offline we return the question unchanged.
            out = prompt.split("QUESTION:", 1)[-1].split("PASSAGE:", 1)[0].strip()
        else:
            out = self._answer(prompt)
        return LLMReply(out, self.model)

    # Level 1: departments, type, urgency, short summary
    def _level1(self, doc: str) -> dict:
        text = doc.lower()
        # The opening lines (title / subject) say what the document is FOR, so they count 3x:
        # a crude version of the routing rule "who must act on it, not which words are most common".
        head = "\n".join(text.strip().splitlines()[:4])
        scores = {d: sum(text.count(k) + 2 * head.count(k) for k in kws) for d, kws in DEPARTMENT_KEYWORDS.items()}
        ranked = [d for d in sorted(scores, key=scores.get, reverse=True) if scores[d]]
        if not ranked:
            departments = [{"name": "Operations", "confidence": 0.2}]
        else:
            top = scores[ranked[0]]
            runner_up = scores[ranked[1]] if len(ranked) > 1 else 0
            departments = [{"name": ranked[0], "confidence": round(min(0.95, top / (top + runner_up)), 2)}]
            departments += [{"name": d, "confidence": round(scores[d] / (top + runner_up), 2)}
                            for d in ranked[1:3] if scores[d] >= top / 2]
        if re.search(r"with immediate effect|critical|derail|fatal", text):
            urgency = "Critical"
        elif re.search(r"urgent|immediately|within 24|within 48", text):
            urgency = "High"
        else:
            urgency = "Medium"
        doc_type = next((label for word, label in DOC_TYPES if word in text), "Document")
        if re.search(r"[\u0D00-\u0D7F]", doc):
            language = "Malayalam + English"
        elif re.search(r"[\u0900-\u097F]", doc):
            language = "Hindi + English"
        else:
            language = "English"
        hits = scores[ranked[0]] if ranked else 0
        return {
            "departments": departments,
            "doc_type": doc_type,
            "urgency": urgency,
            "language": language,
            "summary": " ".join([s for s in sentences(doc) if len(s.split()) >= 8][:2])[:400] or doc.strip()[:400],
            "reasoning": f"Offline keyword rules: {hits} weighted keyword hits for {departments[0]['name']} "
                         f"(title words count 3x).",
            "why_not": (f"{ranked[1]} scored {scores[ranked[1]]}, lower than {hits}." if len(ranked) > 1 else ""),
        }

    # Level 2: entities found with regexes over the chunks
    def _level2(self, prompt: str) -> dict:
        level1 = json.loads(prompt.split("LEVEL1_RESULT:", 1)[1].split("CHUNKS:", 1)[0])
        text = prompt.split("CHUNKS:", 1)[-1]
        vendors = {m.strip() for m in VENDOR_RE.findall(text) if "Kochi Metro" not in m}
        actions = []
        for s in sentences(text):
            if ACTION_RE.search(s):
                due = DUE_RE.search(s)
                actions.append({"action": s[:200], "owner": None,
                                "priority": "High" if level1["urgency"] in ("High", "Critical") else "Medium",
                                "due": due.group(1) if due else None, "confidence": 0.6})
        deadline = next((DATE_RE.search(s).group(0) for s in sentences(text)
                         if DATE_RE.search(s) and re.search(r"\b(due|by|before|last date|deadline)\b", s, re.I)), None)
        return {
            "dates": [{"value": d, "confidence": 0.9} for d in dict.fromkeys(DATE_RE.findall(text))],
            "amounts": [{"value": a, "confidence": 0.9} for a in dict.fromkeys(AMOUNT_RE.findall(text))],
            "reference_ids": [{"value": r, "confidence": 0.85} for r in dict.fromkeys(REF_ID_RE.findall(text))],
            "vendors": [{"value": v, "confidence": 0.7} for v in sorted(vendors)],
            "action_items": actions[:5],
            "deadline": deadline,
            "compliance_required": bool(re.search(r"cmrs|compliance|statutory", text, re.I)),
        }

    # RAG answer: pick one sentence from a chunk that is clearly about the question
    def _answer(self, prompt: str) -> str:
        context = prompt.split("<documents>", 1)[-1].split("</documents>", 1)[0]
        question = prompt.split("QUESTION:", 1)[-1].split("ANSWER:", 1)[0]
        q_stems = stems(question) - QUESTION_WORDS
        best, best_overlap = None, 0
        for n, body in re.findall(r"\[(\d+)\] \([^)]*\)\n(.*?)(?=\n\[\d+\] \(|\Z)", context, re.S):
            # 1. the chunk must cover at least 60% of the question's words (on topic)
            if len(q_stems & stems(body)) < 0.6 * len(q_stems):
                continue
            # 2. inside it, the sentence sharing the most words wins (shorter wins a tie)
            for sentence in SENTENCE_RE.split(body.strip()):
                overlap = len(q_stems & stems(sentence))
                if overlap > best_overlap or (overlap == best_overlap and best and len(sentence) < len(best)):
                    best, best_overlap = f"{sentence.strip()} [{n}]", overlap
        if best is None or best_overlap < min(2, len(q_stems)):
            return "Not found in the documents."
        return best

    def decide(self, text: str, questions: list[dict]) -> dict:
        """Offline stand-in for the Decisions API: keyword scores turned into shares (not real probabilities)."""
        answers = []
        for q in questions:
            values = [c["value"] for c in q["choices"]]
            scores = {v: s["score"] for v, s in keyword_scores(text).items() if v in values}
            total = sum(scores.values()) or 1
            probs = [{"value": v, "probability": round(scores.get(v, 0) / total, 2)} for v in values]
            best = max(probs, key=lambda p: p["probability"])
            answers.append({"type": "choice", "name": q["name"], "choice": best["value"],
                            "probabilities": probs, "confidence": best["probability"]})
        return {"model": "offline-keyword-shares", "answers": answers, "usage": {"input_tokens": 0}}

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        """Feature hashing: each word adds 1 to a bucket chosen by its hash."""
        vectors = []
        for text in texts:
            vec = np.zeros(OFFLINE_DIM, dtype=np.float32)
            for word in re.findall(r"[a-z0-9₹]+", text.lower()):
                vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % OFFLINE_DIM] += 1.0
            vectors.append(normalize(vec))
        return vectors


def get_provider():
    if settings.use_openai:
        return OpenAIProvider(settings.openai_api_key, settings.openai_model, settings.openai_embed_model)
    return OfflineProvider()
