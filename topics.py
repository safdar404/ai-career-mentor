"""Fixed topic taxonomy.

Agents must tag every question and every gap with one of these keys. A fixed
vocabulary is what makes "repeated weakness" detection reliable: the same gap
always lands on the same key instead of on slightly different free-text labels.
"""
from __future__ import annotations

TOPIC_GROUPS: dict[str, dict[str, str]] = {
    "python": {
        "python.fundamentals": "Variables, data types, operators, control flow",
        "python.data_structures": "Lists, tuples, sets, dictionaries",
        "python.functions": "Functions, arguments, scope, lambdas",
        "python.oop": "Classes, inheritance, encapsulation, dunder methods",
        "python.exceptions": "Exception handling and custom exceptions",
        "python.files": "File handling and context managers",
        "python.comprehensions": "List/dict/set comprehensions",
        "python.generators": "Iterators and generators",
        "python.decorators": "Decorators",
        "python.modules": "Modules, packages, virtual environments",
    },
    "python_libs": {
        "libs.numpy": "NumPy arrays and vectorisation",
        "libs.pandas": "Pandas data manipulation and cleaning",
        "libs.matplotlib": "Matplotlib visualisation",
        "libs.apis": "Calling REST APIs from Python (requests/httpx)",
    },
    "ml": {
        "ml.supervised": "Supervised learning",
        "ml.unsupervised": "Unsupervised learning",
        "ml.regression_classification": "Regression vs classification",
        "ml.evaluation": "Model training and evaluation metrics",
        "ml.overfitting": "Overfitting, underfitting, regularisation",
        "ml.features": "Feature engineering",
        "ml.deep_learning": "Neural networks and deep learning fundamentals",
    },
    "genai": {
        "genai.transformers": "Transformer architecture and attention",
        "genai.tokenization": "Tokens, tokenization, context windows",
        "genai.embeddings": "Embeddings and semantic similarity",
        "genai.prompting": "Prompt engineering",
        "genai.sampling": "Temperature and sampling",
        "genai.llm_apis": "Using LLM APIs in applications",
        "genai.hallucinations": "Hallucinations and grounding",
        "genai.rag": "Retrieval-Augmented Generation architecture",
        "genai.vector_db": "Vector databases, chunking, retrieval",
        "genai.fine_tuning": "Fine-tuning vs RAG vs prompting",
        "genai.evaluation": "Evaluating LLM applications",
    },
    "agentic": {
        "agentic.agents_vs_chatbots": "AI agents vs traditional chatbots",
        "agentic.architecture": "Agent architecture, planning, reasoning loops",
        "agentic.tool_calling": "Tool / function calling",
        "agentic.memory": "Agent memory",
        "agentic.multi_agent": "Multi-agent collaboration and orchestration",
        "agentic.hitl": "Human-in-the-loop",
        "agentic.evaluation": "Agent evaluation",
        "agentic.safety": "Agent security and reliability",
    },
    "app_dev": {
        "app.streamlit": "Streamlit applications",
        "app.rest_fastapi": "REST APIs and FastAPI",
        "app.architecture": "Application architecture, frontend/backend integration",
        "app.config_auth": "Environment variables, secrets, authentication",
        "app.error_handling": "Error handling in applications",
        "app.system_design": "System design for AI applications",
    },
    "deployment": {
        "docker.basics": "Containers, images, Dockerfiles",
        "docker.compose": "Docker Compose, networking, volumes, ports",
        "deploy.cloud": "Cloud deployment",
        "deploy.monitoring": "Production monitoring and logging",
    },
    "automation": {
        "auto.platforms": "n8n, Zapier, Make.com",
        "auto.triggers_webhooks": "Triggers, actions, webhooks",
        "auto.workflows": "Conditional workflows and error handling",
        "auto.ai_automation": "AI-powered business automation",
    },
    "industry": {
        "eng.git": "Git and GitHub",
        "eng.sql": "SQL and databases",
        "eng.testing": "Testing",
        "eng.security": "Security fundamentals",
    },
    "communication": {
        "comm.grammar": "Grammar",
        "comm.vocabulary": "Vocabulary and technical terminology",
        "comm.sentence_structure": "Sentence structure",
        "comm.fluency": "Fluency and clarity",
        "comm.explaining": "Explaining complex ideas simply",
        "comm.professional_tone": "Professional tone",
    },
    "professional": {
        "pro.self_intro": "Self-introduction and career story",
        "pro.behavioral_star": "Behavioral answers (STAR)",
        "pro.project_explanation": "Explaining project architecture",
        "pro.defending_decisions": "Defending technical decisions",
        "pro.problem_solving": "Problem-solving communication",
        "pro.recruiter": "Recruiter and salary conversations",
    },
}

ALL_TOPICS: dict[str, str] = {k: v for group in TOPIC_GROUPS.values() for k, v in group.items()}

GROUP_LABELS = {
    "python": "Python",
    "python_libs": "Python libraries",
    "ml": "Machine learning",
    "genai": "Generative AI",
    "agentic": "Agentic AI",
    "app_dev": "App development",
    "deployment": "Docker & deployment",
    "automation": "Automation",
    "industry": "Engineering practice",
    "communication": "Communication",
    "professional": "Professional",
}


def group_of(topic: str) -> str:
    for group, topics in TOPIC_GROUPS.items():
        if topic in topics:
            return group
    return "other"


def normalize_topic(topic: str | None, fallback: str = "pro.problem_solving") -> str:
    """Map whatever the model returned onto a valid taxonomy key."""
    if not topic:
        return fallback
    t = topic.strip().lower()
    if t in ALL_TOPICS:
        return t
    # tolerate e.g. "rag" or "genai/rag"
    t = t.replace("/", ".").replace(" ", "_")
    if t in ALL_TOPICS:
        return t
    for key in ALL_TOPICS:
        if key.split(".", 1)[1] == t or key.endswith("." + t):
            return key
    return fallback


def taxonomy_prompt_block(groups: list[str] | None = None) -> str:
    lines = []
    for group, topics in TOPIC_GROUPS.items():
        if groups and group not in groups:
            continue
        for key, desc in topics.items():
            lines.append(f"- {key}: {desc}")
    return "\n".join(lines)
