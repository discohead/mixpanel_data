"""GQM (Goal-Question-Metric) investigation tool.

This module provides the gqm_investigation tool that performs
structured analytics investigations using the GQM methodology.

Decomposes high-level goals into operational questions and
executes relevant queries to answer each question.

Example:
    Ask Claude: "Investigate why retention is declining"
    Claude uses: gqm_investigation(goal="understand why retention is declining")
"""

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Literal

from fastmcp import Context

from mp_mcp.context import get_workspace
from mp_mcp.errors import handle_errors
from mp_mcp.server import mcp
from mp_mcp.types import GQMInvestigation, QuestionFinding

# AARRR category keywords for classification
AARRR_KEYWORDS: dict[
    Literal["acquisition", "activation", "retention", "revenue", "referral"],
    list[str],
] = {
    "acquisition": [
        "signup",
        "register",
        "new user",
        "acquisition",
        "first visit",
        "landing",
        "traffic",
        "source",
        "campaign",
        "channel",
    ],
    "activation": [
        "activation",
        "onboarding",
        "first",
        "aha moment",
        "setup",
        "complete profile",
        "engaged",
        "value",
    ],
    "retention": [
        "retention",
        "return",
        "churn",
        "comeback",
        "repeat",
        "staying",
        "leave",
        "leaving",
        "drop-off",
        "inactive",
    ],
    "revenue": [
        "revenue",
        "purchase",
        "payment",
        "conversion",
        "monetization",
        "arpu",
        "ltv",
        "subscription",
        "upgrade",
        "pricing",
    ],
    "referral": [
        "referral",
        "invite",
        "share",
        "viral",
        "word of mouth",
        "recommend",
        "refer",
        "invite",
    ],
}

# Question templates per AARRR category
QUESTION_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "acquisition": [
        {
            "question": "How many new users signed up in this period?",
            "query_type": "segmentation",
        },
        {
            "question": "Which acquisition channels are driving the most signups?",
            "query_type": "property_counts",
        },
        {
            "question": "How has the signup trend changed over time?",
            "query_type": "segmentation",
        },
        {
            "question": "What is the conversion rate from visit to signup?",
            "query_type": "funnel",
        },
    ],
    "activation": [
        {
            "question": "What percentage of new users complete activation?",
            "query_type": "segmentation",
        },
        {
            "question": "How long does activation take on average?",
            "query_type": "segmentation",
        },
        {
            "question": "Which activation steps have the highest drop-off?",
            "query_type": "funnel",
        },
        {
            "question": "Are there user segments that activate faster?",
            "query_type": "property_counts",
        },
    ],
    "retention": [
        {
            "question": "What is the current day-7 retention rate?",
            "query_type": "retention",
        },
        {
            "question": "How has retention changed over time?",
            "query_type": "retention",
        },
        {
            "question": "Which user segments have the best retention?",
            "query_type": "retention",
        },
        {
            "question": "What actions correlate with higher retention?",
            "query_type": "event_counts",
        },
        {
            "question": "When do users typically churn?",
            "query_type": "retention",
        },
    ],
    "revenue": [
        {
            "question": "What is the total revenue this period?",
            "query_type": "segmentation",
        },
        {
            "question": "Which products/features drive the most revenue?",
            "query_type": "property_counts",
        },
        {
            "question": "What is the conversion rate to paid?",
            "query_type": "funnel",
        },
        {
            "question": "How has revenue per user changed?",
            "query_type": "segmentation",
        },
    ],
    "referral": [
        {
            "question": "How many users have referred others?",
            "query_type": "segmentation",
        },
        {
            "question": "What is the viral coefficient?",
            "query_type": "segmentation",
        },
        {
            "question": "Which channels are referred users coming from?",
            "query_type": "property_counts",
        },
        {
            "question": "Do referred users have better retention?",
            "query_type": "retention",
        },
    ],
}


def _get_default_date_range(days_back: int = 30) -> tuple[str, str]:
    """Get default date range for investigation.

    Args:
        days_back: Number of days to look back.

    Returns:
        Tuple of (from_date, to_date) as strings.
    """
    today = datetime.now().date()
    from_date = (today - timedelta(days=days_back)).isoformat()
    to_date = today.isoformat()
    return from_date, to_date


def classify_aarrr_category(
    goal: str,
) -> Literal["acquisition", "activation", "retention", "revenue", "referral"]:
    """Classify a goal into an AARRR category.

    Analyzes the goal text to determine which pirate metrics
    category (Acquisition, Activation, Retention, Revenue, Referral)
    the investigation should focus on.

    Args:
        goal: The user's high-level goal to investigate.

    Returns:
        One of: acquisition, activation, retention, revenue, referral.

    Example:
        >>> classify_aarrr_category("why is user retention declining")
        'retention'
    """
    goal_lower = goal.lower()

    # Score each category based on keyword matches
    scores: dict[str, int] = dict.fromkeys(AARRR_KEYWORDS, 0)

    for category, keywords in AARRR_KEYWORDS.items():
        for keyword in keywords:
            if keyword in goal_lower:
                scores[category] += 1

    # Find the category with highest score
    best_category = max(scores, key=lambda k: scores[k])

    # Default to retention if no clear match (most common investigation type)
    if scores[best_category] == 0:
        return "retention"

    return best_category  # type: ignore[return-value]


def generate_questions(
    goal: str,
    category: Literal["acquisition", "activation", "retention", "revenue", "referral"],
    max_questions: int = 5,
) -> list[dict[str, str]]:
    """Generate investigation questions based on goal and category.

    Produces 3-5 operational questions that will help answer the
    user's high-level goal.

    Args:
        goal: The user's high-level goal to investigate.
        category: The AARRR category to focus on.
        max_questions: Maximum number of questions to generate.

    Returns:
        List of question dictionaries with question and query_type.

    Example:
        >>> generate_questions("why is retention declining", "retention", 3)
        [
            {"question": "What is the current day-7 retention rate?", ...},
            {"question": "How has retention changed over time?", ...},
            ...
        ]
    """
    templates = QUESTION_TEMPLATES.get(category, QUESTION_TEMPLATES["retention"])

    # Select questions up to the max
    questions = templates[:max_questions]

    # Add the goal as context to each question
    return [
        {
            **q,
            "context": f"Goal: {goal}",
        }
        for q in questions
    ]


def execute_question_queries(
    ctx: Context,
    questions: list[dict[str, str]],
    from_date: str,
    to_date: str,
    acquisition_event: str = "signup",
) -> list[QuestionFinding]:
    """Execute queries to answer each question.

    Runs the appropriate query for each question and returns
    the findings.

    Args:
        ctx: FastMCP context with workspace access.
        questions: List of questions with query_type.
        from_date: Start date for queries.
        to_date: End date for queries.
        acquisition_event: Event to use for acquisition analysis.

    Returns:
        List of QuestionFinding results.
    """
    ws = get_workspace(ctx)
    findings: list[QuestionFinding] = []

    for q in questions:
        question = q["question"]
        query_type = q.get("query_type", "segmentation")

        try:
            result: dict[str, Any] | None = None

            if query_type == "segmentation":
                # Run segmentation query
                seg_result = ws.segmentation(
                    event=acquisition_event,
                    from_date=from_date,
                    to_date=to_date,
                    unit="day",
                )
                result = seg_result.to_dict()

            elif query_type == "retention":
                # Run retention query
                ret_result = ws.retention(
                    born_event=acquisition_event,
                    return_event=acquisition_event,
                    from_date=from_date,
                    to_date=to_date,
                    unit="day",
                    interval_count=7,
                )
                result = ret_result.to_dict()

            elif query_type == "property_counts":
                # Run property counts query with common property
                prop_result = ws.property_counts(
                    event=acquisition_event,
                    property_name="$browser",  # Default property
                    from_date=from_date,
                    to_date=to_date,
                    limit=10,
                )
                result = prop_result.to_dict()

            elif query_type == "event_counts":
                # Get top events and compare them
                try:
                    events = ws.events()[:5]
                    count_result = ws.event_counts(
                        events=events,
                        from_date=from_date,
                        to_date=to_date,
                    )
                    result = count_result.to_dict()
                except Exception:
                    result = {"error": "Could not execute event_counts query"}

            elif query_type == "funnel":
                # Funnel requires a saved funnel ID, so note it's unavailable
                result = {
                    "note": "Funnel analysis requires a saved funnel ID",
                    "suggestion": "Use list_funnels to find available funnels",
                }

            else:
                result = {"error": f"Unknown query type: {query_type}"}

            findings.append(
                QuestionFinding(
                    question=question,
                    query_type=query_type,
                    status="success",
                    result=result,
                )
            )

        except Exception as e:
            findings.append(
                QuestionFinding(
                    question=question,
                    query_type=query_type,
                    status="failed",
                    error=str(e),
                )
            )

    return findings


def _synthesize_findings(
    goal: str,
    category: str,
    findings: list[QuestionFinding],
) -> dict[str, Any]:
    """Synthesize findings into actionable insights.

    Creates a summary of findings without LLM (for graceful degradation).

    Args:
        goal: The original investigation goal.
        category: The AARRR category.
        findings: Results from executing queries.

    Returns:
        Dictionary with synthesis.
    """
    successful = [f for f in findings if f.status == "success"]
    failed = [f for f in findings if f.status == "failed"]

    synthesis: dict[str, Any] = {
        "goal": goal,
        "category": category,
        "questions_answered": len(successful),
        "questions_failed": len(failed),
    }

    # Extract key metrics from successful findings
    key_metrics: list[dict[str, Any]] = []
    for finding in successful:
        if finding.result:
            key_metrics.append(
                {
                    "question": finding.question,
                    "query_type": finding.query_type,
                    "has_data": bool(finding.result),
                }
            )

    synthesis["key_metrics"] = key_metrics

    # Generate simple next steps based on category
    next_steps: list[str] = []
    if category == "retention":
        next_steps = [
            "Compare retention across user segments",
            "Identify actions correlated with better retention",
            "Analyze time-to-churn patterns",
        ]
    elif category == "acquisition":
        next_steps = [
            "Analyze channel-specific conversion rates",
            "Compare cost per acquisition by channel",
            "Identify highest-value acquisition sources",
        ]
    elif category == "activation":
        next_steps = [
            "Map the activation funnel steps",
            "Identify friction points in onboarding",
            "Compare activation rates by user segment",
        ]
    elif category == "revenue":
        next_steps = [
            "Analyze revenue by product/feature",
            "Calculate customer lifetime value",
            "Identify upsell opportunities",
        ]
    elif category == "referral":
        next_steps = [
            "Track referral source performance",
            "Calculate viral coefficient",
            "Compare referred vs organic user behavior",
        ]

    synthesis["next_steps"] = next_steps

    return synthesis


@mcp.tool
@handle_errors
def gqm_investigation(
    ctx: Context,
    goal: str,
    from_date: str | None = None,
    to_date: str | None = None,
    acquisition_event: str = "signup",
    max_questions: int = 5,
) -> dict[str, Any]:
    """Perform structured investigation using GQM methodology.

    Decomposes a high-level goal into operational questions,
    executes relevant queries, and synthesizes findings.

    Uses the Goal-Question-Metric methodology to systematically
    investigate analytics questions.

    Args:
        ctx: FastMCP context with workspace access.
        goal: High-level goal to investigate (e.g., "understand why retention is declining").
        from_date: Start date for analysis (YYYY-MM-DD). Defaults to 30 days ago.
        to_date: End date for analysis (YYYY-MM-DD). Defaults to today.
        acquisition_event: Event to use for analysis (default: "signup").
        max_questions: Maximum questions to generate (default: 5).

    Returns:
        Dictionary containing:
        - interpreted_goal: Clarified version of the goal
        - aarrr_category: Classification (acquisition/activation/retention/revenue/referral)
        - period: Analysis date range
        - questions: Generated sub-questions
        - findings: Query results for each question
        - synthesis: Summary of insights
        - next_steps: Suggested follow-up investigations

    Example:
        Ask: "Investigate why retention is declining"
        Uses: gqm_investigation(goal="understand why retention is declining")

        Ask: "Why are signups down this month?"
        Uses: gqm_investigation(
            goal="understand why signups decreased",
            from_date="2026-01-01",
            to_date="2026-01-31",
        )
    """
    # Set default date range
    if not from_date or not to_date:
        from_date, to_date = _get_default_date_range()

    # Step 1: Classify the goal into an AARRR category
    category = classify_aarrr_category(goal)

    # Step 2: Generate questions
    questions = generate_questions(goal, category, max_questions)

    # Step 3: Get schema context
    ws = get_workspace(ctx)
    schema_context: dict[str, Any] = {}
    try:
        events = ws.events()[:20]
        schema_context["available_events"] = events
    except Exception:
        schema_context["available_events"] = []

    try:
        funnels = ws.funnels()
        schema_context["available_funnels"] = len(funnels)
    except Exception:
        schema_context["available_funnels"] = 0

    # Step 4: Execute queries
    findings = execute_question_queries(
        ctx, questions, from_date, to_date, acquisition_event
    )

    # Step 5: Synthesize findings
    synthesis = _synthesize_findings(goal, category, findings)

    # Build the result
    investigation = GQMInvestigation(
        interpreted_goal=goal,
        aarrr_category=category,
        period={"from_date": from_date, "to_date": to_date},
        schema_context=schema_context,
        questions=questions,
        findings=[asdict(f) for f in findings],  # type: ignore[misc]
        synthesis=synthesis,
        next_steps=synthesis.get("next_steps", []),
    )

    return asdict(investigation)
