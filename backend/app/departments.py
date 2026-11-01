"""The eight KMRL departments: what each one OWNS, and where its boundary is.

One table, used in four places so they can never disagree:
  - the Level 1 prompt (the model reads these definitions),
  - the offline classifier and the per-chunk signals (the keywords),
  - the API  GET /departments  and the UI's "What each department owns" panel,
  - the eval labels.

THE ROUTING RULE: a document goes to the department that must ACT on it
(its main purpose), not the department whose words appear most often.
A repair work order that contains a cost table is still Maintenance.
"""

DEPARTMENT_DEFINITIONS = {
    "Engineering": {
        "owns": "Design and construction of fixed assets: track, viaduct, signalling and electrical design, drawings, civil works.",
        "not": "Routine upkeep of existing assets (Maintenance).",
        "keywords": ["signal", "track", "viaduct", "electrical", "drawing", "design", "civil"],
    },
    "Operations": {
        "owns": "Running the train service: timetables, headways, station staffing, passenger flow, ridership.",
        "not": "Incidents and statutory safety orders (Safety).",
        "keywords": ["timetable", "passenger", "headway", "ridership", "train service", "station staff"],
    },
    "Maintenance": {
        "owns": "Keeping rolling stock and equipment working: work orders, repairs, overhauls, preventive maintenance, depot jobs.",
        "not": "Paying for the work (Finance) or buying the parts (Procurement), even when costs are listed.",
        "keywords": ["maintenance", "repair", "rolling stock", "overhaul", "bogie", "preventive", "depot",
                     "work order"],
    },
    "Safety": {
        "owns": "Incidents, hazards, safety circulars, CMRS directions, fire and evacuation, mandatory safety checks.",
        "not": "Ordinary repairs with no safety order behind them (Maintenance).",
        "keywords": ["safety", "incident", "fire", "evacuation", "cmrs", "hazard", "emergency", "accident"],
    },
    "Finance": {
        "owns": "Documents whose main purpose is money: invoices to pay, payment reminders, budgets, GST, revenue.",
        "not": "Documents that only mention a cost while asking for other work (route to the department doing the work).",
        "keywords": ["invoice", "payment", "budget", "gst", "payable", "revenue", "₹", "rs."],
    },
    "HR": {
        "owns": "People matters: recruitment, leave, salary, attendance, staff training.",
        "not": "Safety drills ordered by a safety circular (Safety).",
        "keywords": ["employee", "recruitment", "leave", "training", "salary", "attendance"],
    },
    "Legal": {
        "owns": "Contracts, agreements, amendments, clauses, disputes, court and arbitration matters.",
        "not": "Buying decisions and tenders (Procurement).",
        "keywords": ["contract", "agreement", "clause", "legal", "court", "arbitration"],
    },
    "Procurement": {
        "owns": "Buying: tenders, bids, quotations, purchase orders, supplier selection.",
        "not": "Paying an invoice for goods already delivered (Finance).",
        "keywords": ["tender", "purchase order", "supplier", "quotation", "procurement", "bid"],
    },
}

DEPARTMENTS = list(DEPARTMENT_DEFINITIONS)
KEYWORDS = {name: d["keywords"] for name, d in DEPARTMENT_DEFINITIONS.items()}
ROUTING_RULE = ("Route to the department that must ACT on the document (its main purpose), "
                "not the one whose words appear most often.")


def definitions_for_prompt() -> str:
    lines = [f"- {name}: owns {d['owns']} NOT: {d['not']}" for name, d in DEPARTMENT_DEFINITIONS.items()]
    return "\n".join(lines)


def keyword_scores(text: str) -> dict[str, dict]:
    """Count each department's keywords in a piece of text. Used per chunk (and offline per document)."""
    low = text.lower()
    out = {}
    for name, words in KEYWORDS.items():
        hits = {w: low.count(w) for w in words if low.count(w)}
        if hits:
            out[name] = {"score": sum(hits.values()), "words": hits}
    return out
