"""LLM + embedding providers behind one small interface.

GeminiProvider   real model calls over REST (key stays on the server).
OfflineProvider  no network: keyword rules + hashed bag-of-words vectors.
                 Lets the demo run on a laptop with no internet, and makes tests
                 deterministic. Swap providers with LLM_PROVIDER in .env.

Both expose:
    generate_json(prompt) -> dict      (JSON mode; caller validates with Pydantic)
    generate_text(prompt) -> str
    embed(texts, task)    -> list[np.ndarray]   task = "document" | "query"
"""
import hashlib
import json
import re

import numpy as np
import requests

from ..config import DEPARTMENTS, settings

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
EMBED_DIM = 768


class LLMError(RuntimeError):
    pass


def normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    return vec if norm == 0 else vec / norm


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, embed_model: str):
        self.api_key = api_key
        self.model = model
        self.embed_model = embed_model

    def _post(self, url: str, body: dict) -> dict:
        # Key goes in a header, not the URL, so it never shows up in logs.
        resp = requests.post(url, json=body, timeout=60,
                             headers={"x-goog-api-key": self.api_key})
        if resp.status_code != 200:
            raise LLMError(f"Gemini {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def _generate(self, prompt: str, json_mode: bool) -> str:
        config = {"temperature": 0.1}
        if json_mode:
            config["responseMimeType"] = "application/json"
        data = self._post(
            f"{GEMINI_BASE}/{self.model}:generateContent",
            {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": config},
        )
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected Gemini response: {str(data)[:300]}") from exc

    def generate_json(self, prompt: str) -> dict:
        text = self._generate(prompt, json_mode=True)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Model did not return valid JSON: {exc}") from exc

    def generate_text(self, prompt: str) -> str:
        return self._generate(prompt, json_mode=False).strip()

    def embed(self, texts: list[str], task: str = "document") -> list[np.ndarray]:
        task_type = "RETRIEVAL_QUERY" if task == "query" else "RETRIEVAL_DOCUMENT"
        vectors: list[np.ndarray] = []
        for start in range(0, len(texts), 100):          # API batch limit is 100
            batch = texts[start:start + 100]
            data = self._post(
                f"{GEMINI_BASE}/{self.embed_model}:batchEmbedContents",
                {"requests": [{
                    "model": f"models/{self.embed_model}",
                    "content": {"parts": [{"text": t}]},
                    "taskType": task_type,
                    "outputDimensionality": EMBED_DIM,
                } for t in batch]},
            )
            vectors += [normalize(np.array(e["values"], dtype=np.float32))
                        for e in data["embeddings"]]
        return vectors


# Keywords per department for the offline classifier.
DEPARTMENT_KEYWORDS = {
    "Engineering": ["signal", "track", "viaduct", "electrical", "drawing", "design", "traction", "civil"],
    "Operations": ["schedule", "timetable", "passenger", "station", "headway", "service", "ridership"],
    "Maintenance": ["maintenance", "repair", "inspection", "rolling stock", "overhaul", "bogie", "preventive"],
    "Safety": ["safety", "incident", "fire", "evacuation", "cmrs", "hazard", "emergency", "accident"],
    "Finance": ["invoice", "payment", "budget", "gst", "amount", "revenue", "₹", "rs."],
    "HR": ["employee", "recruitment", "leave", "training", "staff", "salary", "attendance"],
    "Legal": ["contract", "agreement", "clause", "legal", "court", "notice", "arbitration"],
    "Procurement": ["tender", "purchase order", "vendor", "supplier", "quotation", "procurement", "bid"],
}


class OfflineProvider:
    """Deterministic stand-in for the LLM. Simple on purpose: easy to explain."""
    name = "offline"

    def generate_json(self, prompt: str) -> dict:
        original = prompt.split("DOCUMENT:", 1)[-1].strip()
        text = original.lower()
        scores = {d: sum(text.count(k) for k in kws) for d, kws in DEPARTMENT_KEYWORDS.items()}
        ranked = sorted(scores, key=scores.get, reverse=True)
        top, total = ranked[0], sum(scores.values()) or 1
        urgency = "High" if re.search(r"urgent|immediate|within 48|critical", text) else "Medium"
        sentences = [" ".join(s.split()) for s in re.split(r"(?<=[.!?])\s+|\n\s*\n", original)
                     if len(s.split()) > 4]
        return {
            "department": top if scores[top] else "Operations",
            "secondary_departments": [d for d in ranked[1:3] if scores[d]],
            "confidence": round(scores[top] / total, 2) if scores[top] else 0.2,
            "reasoning": f"Keyword match (offline mode): {scores[top]} hits for {top}.",
            "doc_type": "Document",
            "summary": " ".join(sentences[:2])[:400] or original[:400],
            "key_points": sentences[:3],
            "urgency": urgency,
            "action_items": [],
            "deadline": None,
            "compliance_required": "cmrs" in text or "compliance" in text,
            "vendors": [],
            "amounts": re.findall(r"(?:₹|Rs\.?)\s?[\d,]+", original)[:5],
        }

    def generate_text(self, prompt: str) -> str:
        """Extractive answer: the context sentence sharing the most words with the question."""
        context = prompt.split("CONTEXT:", 1)[-1].split("QUESTION:", 1)[0]
        question = prompt.split("QUESTION:", 1)[-1].split("ANSWER:", 1)[0]
        q_words = set(re.findall(r"[a-z0-9]{3,}", question.lower()))
        best, best_score = None, 0
        for n, body in re.findall(r"\[(\d+)\] \([^)]*\)\n(.*?)(?=\n\[\d+\] \(|\Z)", context, re.S):
            for sentence in re.split(r"(?<=[.!?])\s+", body.strip()):
                overlap = len(q_words & set(re.findall(r"[a-z0-9]{3,}", sentence.lower())))
                score = overlap - len(sentence) / 1000     # ties go to the shorter sentence
                if score > best_score:
                    best, best_score = f"{sentence.strip()} [{n}]", score
        return best or "Not found in the documents."

    def embed(self, texts: list[str], task: str = "document") -> list[np.ndarray]:
        """Feature hashing: each word adds 1 to a bucket chosen by its hash."""
        vectors = []
        for text in texts:
            vec = np.zeros(EMBED_DIM, dtype=np.float32)
            for word in re.findall(r"[a-z0-9₹]+", text.lower()):
                bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBED_DIM
                vec[bucket] += 1.0
            vectors.append(normalize(vec))
        return vectors


def get_provider():
    if settings.use_gemini:
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model,
                              settings.gemini_embed_model)
    return OfflineProvider()


__all__ = ["get_provider", "LLMError", "DEPARTMENTS", "EMBED_DIM"]
