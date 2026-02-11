"""
CLI Demo — Interactive terminal chat with AI Co-workers.
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage, AIMessage

from app.engine.graph import engine
from app.engine.state import DEFAULT_TASK_PROGRESS
from app.api.middleware.safety import check_safety

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"

AGENT_COLORS = {
    "CEO": Colors.BLUE,
    "CHRO": Colors.GREEN,
    "RegionalManager": Colors.CYAN,
    "Mentor": Colors.YELLOW,
    "System": Colors.RED,
}

AGENT_NAMES = {
    "CEO": "CEO (Marco Bizzarri)",
    "CHRO": "CHRO (Elena Rossi)",
    "RegionalManager": "Regional Mgr (Sophie Dubois)",
    "Mentor": "Mentor",
    "System": "System",
}

def print_banner():
    """Print the welcome banner."""
    print(f"""
{Colors.BOLD}{'='*65}
   AI CO-WORKER ENGINE — Interactive Demo
   Simulation: Gucci Group — HRM Talent & Leadership Dev 2.0
{'='*65}{Colors.END}

{Colors.YELLOW}Available Co-workers:{Colors.END}
  CEO          — Strategy, Group DNA, Brand Autonomy
  CHRO         — Competency Framework, Talent, 360° Feedback
  Regional Mgr — Europe Rollout, Training, Local Challenges

{Colors.YELLOW}Commands:{Colors.END}
  /status   — View task progress
  /quit     — Exit the simulation

{Colors.CYAN}Tip: Just type naturally. The Supervisor will route your message
to the right co-worker automatically.{Colors.END}
{'─'*65}
""")

def print_progress(task_progress: dict):
    """Print task completion status."""
    print(f"\n{Colors.BOLD}Task Progress:{Colors.END}")
    for task, done in task_progress.items():
        icon = "[x]" if done else "[ ]"
        print(f"  {icon} {task.replace('_', ' ').title()}")
    completed = sum(1 for v in task_progress.values() if v)
    total = len(task_progress)
    print(f"\n  Progress: {completed}/{total} ({int(completed/total*100)}%)")
    print()

def main():
    """Run the interactive CLI demo."""
    print_banner()

    # Session state
    messages = []
    previous_speaker = ""
    sentiment_score = 0.5
    turn_count = 0
    stuck_counter = 0
    task_progress = DEFAULT_TASK_PROGRESS.copy()

    while True:
        try:
            # Get user input
            user_input = input(f"{Colors.BOLD}You: {Colors.END}").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() == "/quit":
                print(f"\n{Colors.YELLOW}Simulation ended. Great job!{Colors.END}")
                print_progress(task_progress)
                break

            if user_input.lower() == "/status":
                print_progress(task_progress)
                continue

            # Safety check
            safety = check_safety(user_input)
            if not safety["is_safe"]:
                print(f"\n{Colors.RED}[{safety['blocked_reason']}]{Colors.END}")
                print(f"{Colors.RED}   Please stay focused on the simulation.{Colors.END}\n")
                continue

            # Build graph input
            graph_input = {
                "messages": messages + [HumanMessage(content=user_input)],
                "user_message": user_input,
                "next_speaker": "",
                "previous_speaker": previous_speaker,
                "sentiment_score": sentiment_score,
                "turn_count": turn_count,
                "stuck_counter": stuck_counter,
                "task_progress": task_progress,
                "hint_triggered": False,
                "safety_flagged": False,
            }

            # Run engine
            start = time.time()
            print(f"\n{Colors.YELLOW}⏳ Thinking...{Colors.END}", end="", flush=True)

            result = engine.invoke(graph_input)

            elapsed = time.time() - start
            print(f"\r{'':30}\r", end="")  # Clear "Thinking..." line

            # Extract response
            agent_response = ""
            agent_name = "System"
            for msg in reversed(result.get("messages", [])):
                if isinstance(msg, AIMessage):
                    agent_response = msg.content
                    agent_name = msg.additional_kwargs.get("agent_id", "System")
                    break

            # Display response
            color = AGENT_COLORS.get(agent_name, Colors.END)
            display_name = AGENT_NAMES.get(agent_name, agent_name)
            print(f"{color}{Colors.BOLD}{display_name}:{Colors.END}")
            print(f"{color}{agent_response}{Colors.END}")
            print(f"{Colors.YELLOW}   ⏱ {elapsed:.1f}s{Colors.END}\n")

            # Update state
            messages = result.get("messages", messages)
            previous_speaker = result.get("previous_speaker", agent_name)
            sentiment_score = result.get("sentiment_score", sentiment_score)
            turn_count = result.get("turn_count", turn_count)
            stuck_counter = result.get("stuck_counter", stuck_counter)
            task_progress = result.get("task_progress", task_progress)

            # Show hint indicator
            if result.get("hint_triggered"):
                print(f"{Colors.YELLOW}   (Mentor hint was triggered){Colors.END}\n")

        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Interrupted. Goodbye!{Colors.END}")
            break
        except Exception as e:
            print(f"\n{Colors.RED}Error: {e}{Colors.END}\n")

if __name__ == "__main__":
    main()
