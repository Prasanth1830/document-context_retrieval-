import re
import logging
import google.generativeai as genai

logger = logging.getLogger("document-context-retrieval-system")

PATTERNS = [
    "summarize",
    "key_points",
    "question_answering",
    "info_extraction",
    "search_retrieval",
    "comparison",
    "explain",
    "translation",
    "rewrite",
    "generate_content",
    "table_extraction",
    "timeline",
    "action_items",
    "other"
]

# Fast deterministic rules for 0ms pattern matching
RULE_PATTERNS = {
    "summarize": r"\b(summariz|summary|one-page summary|brief overview|overview of|explain this in simple language)\b",
    "key_points": r"\b(key points|main points|important findings|key takeaways|takeaways|main takeaways|remember from this)\b",
    "info_extraction": r"\b(extract|extract all|names|emails|phone numbers|addresses|invoice numbers|contact details)\b",
    "timeline": r"\b(timeline|chronological|dates|list dates|schedule of events|key dates)\b",
    "action_items": r"\b(action items|tasks|deadlines|next steps|to-do|what tasks|deliverables)\b",
    "table_extraction": r"\b(table|tables|excel|tabular|extract tables|data tables)\b",
    "translation": r"\b(translate|translation|in spanish|in hindi|in french|in german)\b",
    "rewrite": r"\b(rewrite|simplify|make it easier|rephrase|professionally)\b",
    "generate_content": r"\b(write an email|create a presentation|generate meeting notes|draft an email|draft notes)\b",
    "comparison": r"\b(compare|difference between|versus|vs)\b",
    "explain": r"\b(explain section|explain paragraph|explain like i'm|what does this mean)\b",
    "search_retrieval": r"\b(find every mention|where does it discuss|show sections about)\b"
}

_COMPILED_RULES = {cat: re.compile(pat, re.I) for cat, pat in RULE_PATTERNS.items()}

def classify_query(user_query: str) -> str:
    q = user_query.strip()
    if not q:
        return "other"
        
    # 1. Fast regex rule matching (0ms latency, zero API cost)
    for cat, regex in _COMPILED_RULES.items():
        if regex.search(q):
            return cat
            
    # 2. LLM Intent Classifier fallback for ambiguous queries
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = f"""
        Classify the following user query into EXACTLY ONE of these categories:
        1. summarize (e.g. 'summarize this document', 'what is this about')
        2. key_points (e.g. 'key points', 'main points', 'important findings')
        3. question_answering (e.g. 'what is the warranty', 'who signed')
        4. info_extraction (e.g. 'extract names', 'dates', 'emails')
        5. search_retrieval (e.g. 'find every mention', 'where does it discuss')
        6. comparison (e.g. 'compare this', 'what is the difference')
        7. explain (e.g. 'explain section 4', 'what does this mean')
        8. translation (e.g. 'translate to english', 'in spanish')
        9. rewrite (e.g. 'rewrite professionally', 'simplify')
        10. generate_content (e.g. 'write email', 'meeting notes')
        11. table_extraction (e.g. 'extract tables', 'convert to excel')
        12. timeline (e.g. 'timeline of events', 'chronological order')
        13. action_items (e.g. 'what tasks need to be completed', 'deadlines')
        14. other (for specific queries that don't fit above)
        
        Output ONLY the category name exactly as written.
        
        User query: {user_query}
        Category:"""
        
        resp = model.generate_content(prompt)
        result = resp.text.strip().lower()
        if result in PATTERNS:
            return result
        return "other"
    except Exception as e:
        logger.error(f"Failed to classify query via LLM: {str(e)}")
        return "other"
