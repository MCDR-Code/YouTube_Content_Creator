"""Stand-in answers for each agent in mock mode, so the whole system runs for free.

The mock Prune server calls answer(agent_id, request) and sends the JSON back exactly like a
real model reply. Answers depend on the week and on the input the agent was given, so each
week is different and the data really flows from one agent to the next.
"""
from __future__ import annotations

import json
import re

TOPICS = [
    {
        "title": "Why do AI chatbots make things up?",
        "why_now": "New chatbot launches keep making headlines for confident wrong answers.",
        "search_terms": ["ai hallucination", "why does chatgpt lie", "llm hallucination explained"],
        "competition": "medium",
        "question": "Why does the chatbot sound so sure when it is wrong?",
        "sections": [
            ("What a hallucination is", "A hallucination is when a language model gives an answer that sounds right but is false. The model is not lying on purpose. It is predicting likely words.",
             ["Language models generate text by predicting the next token."]),
            ("Why it happens", "The model learned patterns from text, not a database of facts. When it has no good pattern, it still produces the most likely sounding words.",
             ["Models are trained to predict text, not to check facts."]),
            ("How to spot it", "Watch for exact numbers, quotes and citations you cannot find anywhere else. Those are the places models invent most often.",
             ["Invented citations are a common form of hallucination."]),
            ("How to reduce it", "Give the model the source text, ask it to quote, and check anything important. Retrieval systems help by putting real documents in front of the model.",
             ["Retrieval-augmented generation supplies documents to the model at answer time."]),
        ],
    },
    {
        "title": "What is a context window?",
        "why_now": "Every new model announcement brags about a bigger context window.",
        "search_terms": ["context window explained", "what is context length", "tokens context window"],
        "competition": "low",
        "question": "Why does the chatbot forget what I said earlier?",
        "sections": [
            ("Tokens first", "Models read text in small pieces called tokens. A token is often part of a word.",
             ["Language models process text as tokens."]),
            ("The window", "The context window is how many tokens the model can look at in one go: your messages, its replies and any documents.",
             ["The context window limits how much text a model can consider at once."]),
            ("Why it forgets", "When a conversation gets longer than the window, the oldest parts fall out or get summarized, so the model can no longer see them.",
             ["Text outside the context window is not visible to the model."]),
            ("Bigger is not always better", "Longer windows cost more and models can still miss details buried in the middle of long text.",
             ["Longer inputs cost more to process."]),
        ],
    },
    {
        "title": "How AI agents use tools",
        "why_now": "Agents that browse, code and book things are the hot topic of the year.",
        "search_terms": ["ai agents explained", "llm tool calling", "what is an ai agent"],
        "competition": "high",
        "question": "What makes an AI agent different from a chatbot?",
        "sections": [
            ("Chatbot versus agent", "A chatbot answers. An agent can also take actions, like searching, running code or calling an app.",
             ["Agents combine a language model with tools."]),
            ("Tool calling", "The model writes a structured request, such as a function name and arguments. Regular code runs the tool and gives the result back.",
             ["In tool calling, the model outputs a structured call that software executes."]),
            ("The loop", "The agent looks at the result and decides the next step, again and again, until the job is done or it hits a limit.",
             ["Agents run in a loop of deciding and acting."]),
            ("Keeping agents safe", "Limit what tools an agent can use, cap its spending, and keep a human approval step for anything that matters.",
             ["Human approval steps reduce the risk of harmful agent actions."]),
        ],
    },
    {
        "title": "RAG explained: giving AI your documents",
        "why_now": "Companies and colleges are building chatbots on their own documents.",
        "search_terms": ["rag explained", "retrieval augmented generation", "chat with your documents"],
        "competition": "medium",
        "question": "How can a chatbot answer questions about my own files?",
        "sections": [
            ("The problem", "A model only knows what was in its training data. It has never seen your syllabus or your company handbook.",
             ["Models do not know private documents they were not trained on."]),
            ("Retrieve", "RAG first searches your documents for the passages most related to the question, often using embeddings.",
             ["Embeddings turn text into numbers so similar passages can be found."]),
            ("Then generate", "Those passages are pasted into the prompt, and the model writes an answer based on them.",
             ["In RAG, retrieved text is added to the prompt before the model answers."]),
            ("Where it fails", "If the search finds the wrong passage, the answer will be wrong too, so retrieval quality matters most.",
             ["RAG answers depend on the quality of retrieval."]),
        ],
    },
    {
        "title": "Small AI models that run on your phone",
        "why_now": "Phone makers are shipping AI that works without the internet.",
        "search_terms": ["on device ai", "small language model", "ai without internet"],
        "competition": "low",
        "question": "Can AI work on my phone without the cloud?",
        "sections": [
            ("Big and small models", "The biggest models need data centers. Smaller models trade some skill for being able to run on a laptop or phone.",
             ["Smaller models can run on consumer devices."]),
            ("How they shrink", "Tricks like quantization store each number with fewer bits, which cuts memory use a lot.",
             ["Quantization reduces the memory a model needs."]),
            ("Why it matters", "Running on the device can be faster, cheaper and more private, because your data does not leave the phone.",
             ["On-device processing can keep data on the device."]),
            ("The limits", "Small models know less and make more mistakes on hard questions, so many apps still mix local and cloud models.",
             ["Smaller models are generally less capable than the largest models."]),
        ],
    },
    {
        "title": "How AI image generators work",
        "why_now": "AI images are everywhere, and people want to know how to spot them.",
        "search_terms": ["how ai image generation works", "diffusion model explained", "ai art explained"],
        "competition": "high",
        "question": "How does AI turn words into a picture?",
        "sections": [
            ("Starting from noise", "Diffusion models start with random noise and remove it step by step until a picture appears.",
             ["Diffusion models generate images by gradually removing noise."]),
            ("Guided by text", "A text encoder turns your prompt into numbers that steer each step toward matching the words.",
             ["Text prompts guide diffusion models through a text encoder."]),
            ("Trained on pairs", "They learned from huge sets of images with captions, which is also why copyright questions come up.",
             ["Image models are trained on images paired with text."]),
            ("Spotting them", "Look for odd hands, warped text and content credentials labels, though detection is getting harder.",
             ["Some platforms label AI-generated images."]),
        ],
    },
]

COMMENT_QUESTIONS = [
    ("Why does the chatbot sound so sure when it is wrong?", "hallucination"),
    ("Why does the chatbot forget what I said earlier?", "context window"),
    ("What makes an AI agent different from a chatbot?", "agents"),
    ("How can a chatbot answer questions about my own files?", "rag"),
    ("Can AI work on my phone without the cloud?", "on-device"),
    ("How does AI turn words into a picture?", "image generation"),
]


def topic_for_week(week: int) -> dict:
    return TOPICS[(week - 1) % len(TOPICS)]


def topic_by_title(title: str) -> dict:
    for t in TOPICS:
        if t["title"].lower() in title.lower() or title.lower() in t["title"].lower():
            return t
    return TOPICS[0]


def extract_input(text: str) -> dict:
    """Pull the JSON our workflows put between <input> tags."""
    m = re.search(r"<input>\s*(\{.*?\})\s*</input>", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}


def answer(agent_id: str, week: int, user_text: str, wants_orders: bool, phase: str = "") -> dict:
    data = extract_input(user_text)
    t = topic_for_week(week)

    if agent_id == "director" and wants_orders:
        return {"orders": [
            {"agent_name": "Trend Scout", "task": f"List 5 rising AI and tech topics for week {week} with search terms."},
            {"agent_name": "Audience Analyst", "task": "Summarize the questions viewers asked in last week's comments."},
            {"agent_name": "Monetization Manager", "task": "Check the candidate topics for sponsor, affiliate and membership fit."},
        ]}

    if agent_id == "trend_scout":
        ranked = [topic_for_week(week + i) for i in range(5)]
        return {"topics": [{k: x[k] for k in ("title", "why_now", "search_terms", "competition")} for x in ranked]}

    if agent_id == "audience_analyst":
        block = re.search(r"<comments>(.*?)</comments>", user_text, re.S)
        comments = re.findall(r"^- (.*)$", block.group(1), re.M) if block else []
        suspicious = sum(1 for c in comments if re.search(r"ignore (all|previous)|system prompt|approve", c, re.I))
        qs = [{"question": q, "times_asked": max(1, sum(1 for c in comments if hint.split()[0] in c.lower())),
               "topic_hint": hint} for q, hint in COMMENT_QUESTIONS]
        qs.sort(key=lambda q: -q["times_asked"])
        return {"questions": qs[:4],
                "retention_notes": "Viewers drop when the intro runs past 30 seconds; examples keep them watching.",
                "suspicious_comments": suspicious}

    if agent_id == "monetization_manager" and phase == "review":
        return {"summary": f"Week {week}: the channel is still building toward the Partner Program. "
                           "Affiliate links on tool-focused videos brought most of the small income.",
                "recommendations": [
                    "Make next week's topic one that viewers asked about in comments, since those videos kept people watching longest.",
                    "Keep the winning title style and test a new thumbnail color.",
                    "Pitch one AI tool company for a clearly disclosed sponsorship on the agents video.",
                ],
                "sponsor_leads": ["An AI note-taking app for students", "An online course platform"]}

    if agent_id == "monetization_manager":
        return {"ideas": [{"topic": x["title"], "sponsor_fit": "AI tools for students and teachers",
                           "affiliate_ideas": ["Recommended textbook on AI", "Course on prompt writing"],
                           "membership_angle": "Members get the professor's slides and a monthly Q&A"}
                          for x in (topic_for_week(week), topic_for_week(week + 1))],
                "partner_program_note": "Ads need 1,000 subscribers plus 4,000 watch hours in 12 months "
                                        "or 10 million Shorts views in 90 days; plan for the higher bar from Feb 2027."}

    if agent_id == "director":
        return {"week": week,
                "long_video": {"topic": t["title"], "angle": "Explained by a professor, with a classroom example",
                               "viewer_question": t["question"], "target_minutes": 8,
                               "hook": f"{t['question']} Here is the real reason, in plain words."},
                "shorts": [{"idea": s[0], "hook": f"{s[0]}? Here it is in 30 seconds."} for s in t["sections"][:3]],
                "money_notes": "Add the affiliate book link with a clear disclosure. No sponsor this week.",
                "reasons": "Trending now, asked about in comments, and medium or low competition."}

    if agent_id == "scriptwriter":
        plan = data.get("plan", {})
        tt = topic_by_title(plan.get("long_video", {}).get("topic", t["title"]))
        fixes = data.get("fixes", [])
        sections = []
        for heading, narration, claims in tt["sections"]:
            sections.append({"heading": heading, "narration": narration,
                             "on_screen": heading, "claims": list(claims),
                             "professor_insert": f"[PROFESSOR: add a classroom example about {heading.lower()}]"})
        sources = [{"claim": c, "source": "Course textbook and the model provider's documentation"}
                   for _, _, cs in tt["sections"] for c in cs]
        if not fixes and week % 2 == 1:
            sections[1]["claims"].append("Bigger models never make mistakes.")
        return {"working_title": tt["title"], "hook": plan.get("long_video", {}).get("hook", tt["question"]),
                "sections": sections,
                "call_to_action": "If this helped, subscribe and tell me in the comments what to explain next.",
                "sources": sources}

    if agent_id == "fact_checker":
        in_claims = re.search(r'claims\\?"\s*:\s*\[[^\]]*never make mistakes', user_text)
        bad = ["Bigger models never make mistakes."] if in_claims else []
        if bad:
            return {"verdict": "FAIL",
                    "issues": [{"claim": bad[0], "problem": "False. Larger models still make mistakes.",
                                "fix": "Remove the claim or say larger models make fewer mistakes on some tasks."}],
                    "notes": "Everything else checks out."}
        return {"verdict": "PASS", "issues": [], "notes": "All claims are accurate and sourced."}

    if agent_id == "visual_designer":
        script = data.get("script", {})
        slides = [{"section": "Intro", "title": script.get("working_title", t["title"]),
                   "bullets": [script.get("hook", "")[:80]], "visual_note": "Title card in channel colors"}]
        for s in script.get("sections", []):
            slides.append({"section": s["heading"], "title": s["heading"],
                           "bullets": [c[:70] for c in s.get("claims", [])][:3] or [s["on_screen"]],
                           "visual_note": "Simple diagram, large text"})
        slides.append({"section": "Outro", "title": "Thanks for watching",
                       "bullets": ["Subscribe for more", "Ask your question in the comments"],
                       "visual_note": "End screen"})
        return {"slides": slides,
                "thumbnail": {"main_text": " ".join(script.get("working_title", t["title"]).rstrip("?").split()[-4:]),
                              "style": "Bold white text on navy, teal accent bar"}}

    if agent_id == "packaging_seo":
        script = data.get("script", {})
        title = script.get("working_title", t["title"])
        q = topic_by_title(title)["question"]
        return {"variants": [
                    {"title": title, "thumbnail_text": " ".join(title.rstrip("?").split()[-4:])},
                    {"title": q[:100], "thumbnail_text": "Confident but wrong?" if "sure" in q else " ".join(q.rstrip("?").split()[-4:]) + "?"},
                    {"title": f"{title} (a professor explains)"[:100], "thumbnail_text": "Professor explains"},
                ],
                "description": f"{script.get('hook', '')}\n\nA college professor explains {title.lower()} in plain words.\n\n"
                               "Some links may be affiliate links. If you buy through them, the channel may earn a small commission.\n\n"
                               "This video uses AI tools to help with scripts and slides. Every video is reviewed and approved by the professor.",
                "chapter_titles": ["Intro"] + [s["heading"] for s in script.get("sections", [])] + ["Wrap up"],
                "tags": topic_by_title(title)["search_terms"] + ["ai explained", "professor"],
                "ai_disclosure": True, "made_for_kids": False,
                "sponsor_disclosure": None}

    if agent_id == "shorts_producer":
        script = data.get("script", {})
        out = []
        for s in script.get("sections", [])[:3]:
            out.append({"title": f"{s['heading']} in 30 seconds", "hook": f"{s['heading']}? Here is the short answer.",
                        "script": s["narration"] + " Full video on the channel.",
                        "source_section": s["heading"], "points_to_long_video": True})
        return {"shorts": out}

    if agent_id == "analytics_analyst":
        stats = data.get("stats", {})
        best = stats.get("best_variant_title", "the question-style title")
        return {"summary": f"Week {week}: {stats.get('views', 0)} views and {stats.get('subs_gained', 0)} new subscribers.",
                "what_worked": [f"The title '{best}' got the most clicks.", "Shorts sent viewers to the long video."],
                "what_didnt": ["Viewers left during the longest section."],
                "best_title_variant": best,
                "best_posting_time": stats.get("best_hour", "Friday 6 PM Eastern")}

    return {"error": f"no mock answer for {agent_id}"}
