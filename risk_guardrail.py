"""
risk_guardrail.py

Decides whether a user's query is safe for the RAG bot to answer on its own,
or whether it must be escalated to a human via the Knowledge Transfer queue.

Design goals (why rule-based, not another LLM call):
  - Deterministic & auditable: a compliance officer can read this file and
    know exactly why a query was blocked. That matters a lot more than a
    black-box "the model decided" for HIPAA/financial-advice scenarios.
  - Fast & offline: no extra network round-trip on the hot path.
  - Cheap to extend: add a phrase to a list, don't retrain anything.
"""

import re
from dataclasses import dataclass, field
from enum import Enum


class RiskCategory(str, Enum):
    NONE = "none"
    FINTECH_REVENUE = "fintech_revenue_risk"
    MEDICAL_SAFETY = "medical_safety_risk"
    SELF_HARM_CRISIS = "self_harm_crisis"          # handled separately, see note below
    EMOTIONAL_DISTRESS = "emotional_distress"
    EMOTIONAL_MANIPULATION = "emotional_manipulation"   # pressure/guilt tactics to bypass the bot's limits


class Severity(str, Enum):
    P1_CRITICAL = "P1"   # must never be answered by bot, escalate immediately
    P2_HIGH = "P2"       # escalate, but not life-threatening / acute in nature
    P3_STANDARD = "P3"   # bot can answer normally


@dataclass
class RiskAssessment:
    is_escalation_required: bool
    category: RiskCategory
    severity: Severity
    matched_patterns: list = field(default_factory=list)
    reason: str = ""
    holding_message: str = ""


# ---------------------------------------------------------------------------
# Pattern banks
# ---------------------------------------------------------------------------

FINTECH_REVENUE_PATTERNS = [
    r"\bshould i (invest|buy|sell|short|put my money)\b",
    r"\bwhich (stock|fund|policy|plan) should i\b",
    r"\bam i (eligible|approved|qualified) for\b",
    r"\b(guarantee|guaranteed) (return|profit|approval)\b",
    r"\bhow much (will i get|is my payout|is my refund|is my claim worth)\b",
    r"\b(waive|reduce|remove) (my )?(penalty|late fee|interest)\b",
    r"\bincrease my (credit limit|loan amount|credit line)\b",
    r"\bis this (a scam|fraud|money laundering)\b",
    r"\bcan i (sue|take legal action)\b",
    r"\bwhat interest rate will i (get|qualify for)\b",
    r"\bshould i (refinance|take out a loan|cash out)\b",
    r"\btax advice\b|\bhow much tax will i owe\b",
]

MEDICAL_SAFETY_PATTERNS = [
    r"\bwhat (medicine|medication|drug|dose|dosage) should i (take|use)\b",
    r"\b(increase|decrease|stop|change|double) my (dose|dosage|medication|insulin|prescription)\b",
    r"\bcan i (take|combine|mix) .* (with|and) .*(medication|drug|pill)\b",
    r"\bdo i have (cancer|diabetes|covid|a tumor|a heart condition)\b",
    r"\bam i (dying|going to die|having a heart attack|having a stroke)\b",
    r"\bis (this|it) (normal|dangerous|life[- ]threatening)\b",
    r"\bshould i (go to|skip) (the )?(er|emergency room|hospital)\b",
    r"\bwhat('s| is) my diagnosis\b",
    r"\bcan you prescribe\b",
    r"\bis (this|my) lab result (normal|okay|bad|dangerous)\b",
    r"\bhow many (pills|tablets|mg) (should|can) i take\b",
]

SELF_HARM_PATTERNS = [
    r"\b(kill myself|end my life|suicide|want to die|hurt myself)\b",
    r"\bself[- ]harm\b",
]

EMOTIONAL_DISTRESS_PATTERNS = [
    r"\bi('m| am) (scared|terrified|panicking|worried sick|desperate|devastated|falling apart)\b",
    r"\bi('m| am) (so|really|extremely)? ?(anxious|stressed|overwhelmed|panicking)\b",
    r"\bi (feel|feel like i('m| am)) (hopeless|helpless|a failure|giving up|drowning|stuck)\b",
    r"\bi don'?t know (what to do|how to cope|how i'?ll cope)\b",
    r"\bi can'?t (stop crying|sleep|think straight|cope|handle this) (anymore|any ?more)?\b",
    r"\bthis is (destroying|ruining|breaking) me\b",
    r"\bplease help me,? i don'?t know what to do\b",
    r"\bi feel so (alone|lost|ashamed|judged)\b",

    r"\bi can'?t (afford|pay|keep up with)\b",
    r"\bi('m| am) (going to lose|about to lose|scared of losing) (my|the) (house|home|job|business|savings|car)\b",
    r"\bi('m| am) (drowning in|buried in|ashamed of) (debt|bills)\b",
    r"\bi('m| am) (worried|scared) (i'?ll|about) (go(ing)? bankrupt|lose everything|be homeless)\b",
    r"\bwhat happens to my family if i (default|can'?t pay|lose my job)\b",
    r"\bi('m| am) losing sleep over (my|this) (finances|money|debt|bills)\b",

    r"\bi('m| am) (terrified|scared|worried sick) (about|of) (this diagnosis|my results|my scan|my health|dying)\b",
    r"\bi('m| am) losing sleep over (my|this) (diagnosis|results|health|symptoms)\b",
    r"\bi feel like giving up on (my treatment|my health|myself)\b",
    r"\bi('m| am) not sure i can (handle|go through|survive) (this|the treatment|another round)\b",
    r"\bwhat if i don'?t make it\b",
    r"\bi('m| am) scared to (tell|show) my family\b",
]

EMOTIONAL_MANIPULATION_PATTERNS = [
    r"\bif you don'?t (tell|answer|help) me,? i('ll| will)\b",
    r"\bi('ll| will) (hurt myself|end things|do something( bad)?|give up) if you don'?t\b",
    r"\bplease,? i('m| am) begging you\b",
    r"\byou'?re the only one who (can|will) help me\b",
    r"\bno ?(one|body) (will|has to|needs to) know\b",
    r"\bjust between (us|you and me)\b",
    r"\bi won'?t tell anyone( else)?\b",
    r"\b(pretend|act as if) you('re| are) (a|my) (doctor|physician|financial advisor|advisor|lawyer|therapist)\b",
    r"\bact as (a|my) (doctor|physician|financial advisor|advisor|lawyer)\b",
    r"\bhypothetically,? if you were my (doctor|advisor|lawyer)\b",
    r"\bignore (your|the) (rules|restrictions|guidelines|disclaimer|training)\b",
    r"\bi don'?t care about (the disclaimer|your policy|liability|the rules)\b",
    r"\b(stop|quit) (being (so )?careful|giving disclaimers) and (just )?answer\b",
    r"\bthis is an emergency,? just tell me\b",
    r"\bjust give me a (number|dose|dosage|amount|figure)\b",
    r"\byou have to tell me or\b",
    r"\bwhat if i told you i('ll| will) (lose everything|go bankrupt|die|not make it) if you don'?t answer\b",
    r"\bi('m| am) begging you,? (please )?just answer\b",

    r"\bif you don'?t .{0,30}\bi('ll| will) (leave a bad review|report you|sue|go to (the press|social media|the news))\b",
    r"\bi('ll| will) (post|write) (a )?(bad|negative|1-star|one star) review (if|unless) you don'?t\b",
    r"\bi('ll| will) tell everyone (not to use|to avoid) (this company|your company|you|your service) if\b",
    r"\bthis will (go viral|be all over social media) if you don'?t\b",

    r"\byou('ll| will) be (responsible|to blame|liable) if (i|my health)\b",
    r"\bit('s| is) (your|the company'?s) fault if (i|something happens to me)\b",
    r"\bif (i|something) (get(s)? worse|happens to me),? it('s| is) on you\b",
]

_COMPILED = {
    RiskCategory.FINTECH_REVENUE: [re.compile(p, re.I) for p in FINTECH_REVENUE_PATTERNS],
    RiskCategory.MEDICAL_SAFETY: [re.compile(p, re.I) for p in MEDICAL_SAFETY_PATTERNS],
    RiskCategory.SELF_HARM_CRISIS: [re.compile(p, re.I) for p in SELF_HARM_PATTERNS],
    RiskCategory.EMOTIONAL_DISTRESS: [re.compile(p, re.I) for p in EMOTIONAL_DISTRESS_PATTERNS],
    RiskCategory.EMOTIONAL_MANIPULATION: [re.compile(p, re.I) for p in EMOTIONAL_MANIPULATION_PATTERNS],
}

HOLDING_MESSAGE_TEMPLATE = (
    "I'm an AI assistant, and this question needs a person to confirm before I answer. "
    "I've sent it to our team \u2014 someone will typically respond within 2 minutes. "
    "You'll see their answer appear here once it's ready."
)

CRISIS_MESSAGE = (
    "I'm an AI assistant and I'm not able to advise on this. If you're in immediate danger, "
    "please contact local emergency services now, or a crisis line if you're able to. "
    "I'm also flagging this for a human on our team right away."
)


def assess_risk(query: str, document_type: str = "general") -> RiskAssessment:
    q = query.strip()
    if not q:
        return RiskAssessment(False, RiskCategory.NONE, Severity.P3_STANDARD)

    matched = [p.pattern for p in _COMPILED[RiskCategory.SELF_HARM_CRISIS] if p.search(q)]
    if matched:
        return RiskAssessment(
            is_escalation_required=True,
            category=RiskCategory.SELF_HARM_CRISIS,
            severity=Severity.P1_CRITICAL,
            matched_patterns=matched,
            reason="Message contains language associated with self-harm risk.",
            holding_message=CRISIS_MESSAGE,
        )

    matched = [p.pattern for p in _COMPILED[RiskCategory.EMOTIONAL_MANIPULATION] if p.search(q)]
    if matched:
        underlying = []
        if any(p.search(q) for p in _COMPILED[RiskCategory.MEDICAL_SAFETY]):
            underlying.append("medical")
        if any(p.search(q) for p in _COMPILED[RiskCategory.FINTECH_REVENUE]):
            underlying.append("fintech")
        domain_note = f" (also touches: {', '.join(underlying)})" if underlying else ""
        return RiskAssessment(
            is_escalation_required=True,
            category=RiskCategory.EMOTIONAL_MANIPULATION,
            severity=Severity.P1_CRITICAL,
            matched_patterns=matched,
            reason="Message uses pressure, secrecy, or role-play framing to push the bot "
                   "toward an answer it would otherwise decline or escalate" + domain_note + ".",
            holding_message=HOLDING_MESSAGE_TEMPLATE,
        )

    matched = [p.pattern for p in _COMPILED[RiskCategory.MEDICAL_SAFETY] if p.search(q)]
    if matched and document_type in ("medical", "general"):
        return RiskAssessment(
            is_escalation_required=True,
            category=RiskCategory.MEDICAL_SAFETY,
            severity=Severity.P1_CRITICAL,
            matched_patterns=matched,
            reason="Query asks the bot to make a clinical judgment (dosage, diagnosis, "
                   "treatment change) beyond restating what the document says.",
            holding_message=HOLDING_MESSAGE_TEMPLATE,
        )

    matched = [p.pattern for p in _COMPILED[RiskCategory.FINTECH_REVENUE] if p.search(q)]
    if matched and document_type in ("fintech", "general"):
        return RiskAssessment(
            is_escalation_required=True,
            category=RiskCategory.FINTECH_REVENUE,
            severity=Severity.P2_HIGH,
            matched_patterns=matched,
            reason="Query asks for a financial decision, eligibility determination, or "
                   "commitment (approval, guarantee, waiver) rather than a document fact.",
            holding_message=HOLDING_MESSAGE_TEMPLATE,
        )

    matched = [p.pattern for p in _COMPILED[RiskCategory.EMOTIONAL_DISTRESS] if p.search(q)]
    if matched:
        return RiskAssessment(
            is_escalation_required=True,
            category=RiskCategory.EMOTIONAL_DISTRESS,
            severity=Severity.P2_HIGH,
            matched_patterns=matched,
            reason="User expresses significant distress; a human should respond with care.",
            holding_message=HOLDING_MESSAGE_TEMPLATE,
        )

    return RiskAssessment(False, RiskCategory.NONE, Severity.P3_STANDARD)
