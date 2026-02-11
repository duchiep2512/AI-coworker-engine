"""Director Layer — monitors user progress and triggers hints when stuck."""

from app.core.logging import logger
from app.engine.state import AgentState

PROGRESS_SIGNALS = {
    "ceo_consulted": ["dna", "autonomy", "brand identity", "group dna", "mission", "heritage"],
    "chro_consulted": ["competency", "vision", "entrepreneurship", "passion", "trust", "framework", "360"],
    "problem_statement_written": ["problem statement", "key tension", "challenge is", "the problem"],
    "competency_model_drafted": ["junior level", "mid level", "senior level", "behavior indicator"],
    "360_program_designed": ["rater", "anonymity", "coaching", "survey", "feedback"],
    "regional_manager_consulted": ["europe", "regional", "rollout", "france", "italy", "train-the-trainer"],
    "rollout_plan_built": ["phase 1", "phase 2", "pilot", "cascade", "timeline"],
    "kpi_table_defined": ["kpi", "metric", "dashboard", "promotion rate", "mobility rate"],
}

STUCK_THRESHOLD = 3        # Consecutive turns without progress before triggering hint

def detect_progress(state: AgentState) -> dict:
    """
    Scan conversation for signals that a task has been completed.

    Returns:
        Updated task_progress dict.
    """
    progress = state.get("task_progress", {}).copy()
    messages = state.get("messages", [])

    # Scan last 5 messages for task completion signals
    recent_text = " ".join(
        msg.content.lower() for msg in messages[-5:]
    )

    for task_key, keywords in PROGRESS_SIGNALS.items():
        if not progress.get(task_key, False):
            if any(kw in recent_text for kw in keywords):
                progress[task_key] = True
                logger.info(f"Task completed: {task_key}")

    return progress

def detect_sentiment(state: AgentState) -> float:
    """
    Simple heuristic-based sentiment analysis.

    Returns:
        Float between 0.0 (frustrated) and 1.0 (confident).
    """
    user_msg = state.get("user_message", "").lower()

    # Negative signals
    negative_signals = ["i don't know", "confused", "help", "stuck", "what do you mean",
                        "i'm lost", "no idea", "unclear", "don't understand", "??"]
    # Positive signals
    positive_signals = ["great", "thanks", "i think", "my plan is", "here's my proposal",
                        "i propose", "let me try", "i'll create", "makes sense"]

    neg_count = sum(1 for s in negative_signals if s in user_msg)
    pos_count = sum(1 for s in positive_signals if s in user_msg)

    current = state.get("sentiment_score", 0.5)

    # Adjust sentiment
    if neg_count > pos_count:
        return max(0.0, current - 0.15)
    elif pos_count > neg_count:
        return min(1.0, current + 0.1)
    return current

def should_trigger_hint(state: AgentState) -> bool:
    """
    Determine if the Director should trigger a Mentor hint.

    Triggers when:
    1. stuck_counter >= STUCK_THRESHOLD (3 consecutive turns without progress)
    2. sentiment_score < 0.3 (user is frustrated)
    
    NOTE: We do NOT trigger based on total turn_count.
    A user may legitimately chat with agents for many turns.
    Only consecutive unproductive turns matter.
    """
    stuck = state.get("stuck_counter", 0) >= STUCK_THRESHOLD
    frustrated = state.get("sentiment_score", 0.5) < 0.3

    trigger = stuck or frustrated

    if trigger:
        logger.info(
            f"Director triggered hint (stuck={stuck}, frustrated={frustrated})"
        )

    return trigger

def director_check(state: AgentState) -> dict:
    """
    The Director runs AFTER the Supervisor routes and BEFORE the agent responds.

    Updates:
      - task_progress (based on conversation content)
      - sentiment_score
      - stuck_counter (incremented if no progress, reset if progress made)
      - hint_triggered (True if Mentor should intervene)
      - next_speaker (overridden to "Mentor" if hint triggered)
    """
    # 1. Update progress
    old_progress = state.get("task_progress", {}).copy()
    new_progress = detect_progress(state)
    progress_made = old_progress != new_progress

    # 2. Update sentiment
    new_sentiment = detect_sentiment(state)

    # 3. Update stuck counter
    current_stuck = state.get("stuck_counter", 0)
    if progress_made:
        new_stuck = 0  # Reset on progress
    else:
        new_stuck = current_stuck + 1

    # 4. Build updated state
    updates = {
        "task_progress": new_progress,
        "sentiment_score": new_sentiment,
        "stuck_counter": new_stuck,
        "hint_triggered": False,
    }

    # 5. Check if hint should trigger
    # BUT: Do NOT override if user explicitly chose an agent (manual mode)
    user_explicit = state.get("user_explicit_choice", False)
    
    temp_state = {**state, **updates}
    if should_trigger_hint(temp_state) and not user_explicit:
        updates["hint_triggered"] = True
        updates["next_speaker"] = "Mentor"
        updates["stuck_counter"] = 0  # Reset so Mentor doesn't loop forever
        logger.info("Director overriding to Mentor (auto-route mode)")
    elif should_trigger_hint(temp_state) and user_explicit:
        logger.info("Hint conditions met, but user chose agent manually — skipping override")

    return updates
