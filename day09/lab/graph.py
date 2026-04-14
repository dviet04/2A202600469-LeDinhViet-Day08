"""
graph.py — Supervisor Orchestrator
Sprint 1: Supervisor-Worker pattern với routing logic thực tế.

Kiến trúc:
    Input → Supervisor → [retrieval_worker | policy_tool_worker | human_review] → synthesis → Output

Chạy thử:
    python graph.py
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import TypedDict, Literal, Optional

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load env
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────
# 1. Shared State
# ─────────────────────────────────────────────

class AgentState(TypedDict):
    # Input
    task: str

    # Supervisor decisions
    route_reason: str
    risk_high: bool
    needs_tool: bool
    hitl_triggered: bool

    # Worker outputs
    retrieved_chunks: list
    retrieved_sources: list
    policy_result: dict
    mcp_tools_used: list
    worker_io_logs: list

    # Final output
    final_answer: str
    sources: list
    confidence: float

    # Trace & history
    history: list
    workers_called: list
    supervisor_route: str
    latency_ms: Optional[int]
    run_id: str
    question_id: Optional[str]


def make_initial_state(task: str) -> AgentState:
    """Khởi tạo state cho một run mới."""
    return {
        "task": task,
        "route_reason": "",
        "risk_high": False,
        "needs_tool": False,
        "hitl_triggered": False,
        "retrieved_chunks": [],
        "retrieved_sources": [],
        "policy_result": {},
        "mcp_tools_used": [],
        "worker_io_logs": [],
        "final_answer": "",
        "sources": [],
        "confidence": 0.0,
        "history": [],
        "workers_called": [],
        "supervisor_route": "",
        "latency_ms": None,
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "question_id": None,
    }


# ─────────────────────────────────────────────
# 2. Supervisor Node — routing logic thực tế
# ─────────────────────────────────────────────

# Routing rules: keywords → route
POLICY_KEYWORDS = [
    "hoàn tiền", "refund", "flash sale", "license", "license key",
    "subscription", "cấp quyền", "access", "level 2", "level 3", "level 4",
    "admin access", "elevated", "kỹ thuật số", "store credit", "điều kiện hoàn",
    "đã kích hoạt", "phê duyệt", "approval"
]

RETRIEVAL_KEYWORDS = [
    "p1", "sla", "ticket", "escalation", "sự cố", "incident",
    "remote", "leave", "probation", "thử việc", "mật khẩu",
    "password", "tài khoản", "account", "bị khóa", "helpdesk",
    "bước", "quy trình", "thông báo"
]

RISK_KEYWORDS = [
    "khẩn cấp", "emergency", "2am", "urgent", "critical",
    "không rõ", "err-", "p1 lúc", "2 giờ sáng"
]

UNKNOWN_ERROR_PATTERNS = ["err-", "error-", "lỗi mã "]


def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor phân tích task và quyết định:
    1. Route sang worker nào
    2. Có cần MCP tool không
    3. Có risk cao cần HITL không
    """
    task = state["task"].lower()
    state["history"].append(f"[supervisor] received: {state['task'][:80]}")

    route = "retrieval_worker"
    route_reason = "default: retrieval_worker for general questions"
    needs_tool = False
    risk_high = False

    # Check risk keywords
    if any(kw in task for kw in RISK_KEYWORDS):
        risk_high = True

    # Check unknown error codes → human_review
    has_unknown_error = any(pat in task for pat in UNKNOWN_ERROR_PATTERNS)
    if has_unknown_error and not any(kw in task for kw in RETRIEVAL_KEYWORDS + POLICY_KEYWORDS):
        route = "human_review"
        route_reason = "unknown error code (ERR-xxx) without clear context → human review"
    
    # Policy / tool keywords take priority
    elif any(kw in task for kw in POLICY_KEYWORDS):
        route = "policy_tool_worker"
        matched = [kw for kw in POLICY_KEYWORDS if kw in task]
        route_reason = f"task contains policy/access keyword: {matched[:3]}"
        needs_tool = True

    # Explicit retrieval keywords
    elif any(kw in task for kw in RETRIEVAL_KEYWORDS):
        route = "retrieval_worker"
        matched = [kw for kw in RETRIEVAL_KEYWORDS if kw in task]
        route_reason = f"task contains retrieval keyword: {matched[:3]}"

    # Multi-hop: cả hai nhóm keyword
    policy_hit = any(kw in task for kw in POLICY_KEYWORDS)
    retrieval_hit = any(kw in task for kw in RETRIEVAL_KEYWORDS)
    if policy_hit and retrieval_hit:
        route = "policy_tool_worker"
        route_reason = f"multi-hop: policy + retrieval keywords → policy_tool_worker (will also call retrieval)"
        needs_tool = True

    # Thêm risk flag vào reason
    if risk_high:
        route_reason += " | risk_high=True (emergency/unknown context)"

    state["supervisor_route"] = route
    state["route_reason"] = route_reason
    state["needs_tool"] = needs_tool
    state["risk_high"] = risk_high
    state["history"].append(f"[supervisor] → route={route} | reason={route_reason}")

    return state


# ─────────────────────────────────────────────
# 3. Route Decision
# ─────────────────────────────────────────────

def route_decision(state: AgentState) -> Literal["retrieval_worker", "policy_tool_worker", "human_review"]:
    return state.get("supervisor_route", "retrieval_worker")  # type: ignore


# ─────────────────────────────────────────────
# 4. Human Review Node
# ─────────────────────────────────────────────

def human_review_node(state: AgentState) -> AgentState:
    """HITL node — placeholder auto-approve trong lab."""
    state["hitl_triggered"] = True
    state["workers_called"].append("human_review")
    state["history"].append("[human_review] HITL triggered — auto-approved in lab mode")

    print(f"\n⚠️  HITL TRIGGERED")
    print(f"   Task: {state['task']}")
    print(f"   Reason: {state['route_reason']}")
    print(f"   Action: Auto-approving → routing to retrieval\n")

    state["supervisor_route"] = "retrieval_worker"
    state["route_reason"] += " | human approved → retrieval"
    return state


# ─────────────────────────────────────────────
# 5. Worker Wrappers (gọi real workers)
# ─────────────────────────────────────────────

from workers.retrieval import run as retrieval_run
from workers.policy_tool import run as policy_tool_run
from workers.synthesis import run as synthesis_run


def retrieval_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi retrieval worker thực."""
    state["history"].append("[retrieval_worker] starting...")
    state = retrieval_run(state)
    return state


def policy_tool_worker_node(state: AgentState) -> AgentState:
    """
    Wrapper gọi policy/tool worker thực.
    Với câu multi-hop: gọi retrieval trước để lấy context,
    sau đó policy worker phân tích trên context đó.
    """
    state["history"].append("[policy_tool_worker] starting...")

    # Nếu chưa có chunks → gọi retrieval trước để có context
    if not state.get("retrieved_chunks"):
        state["history"].append("[policy_tool_worker] no chunks yet — calling retrieval first")
        state = retrieval_run(state)

    state = policy_tool_run(state)
    return state


def synthesis_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi synthesis worker thực."""
    state["history"].append("[synthesis_worker] starting...")
    state = synthesis_run(state)
    return state


# ─────────────────────────────────────────────
# 6. Build Graph (Python native orchestrator)
# ─────────────────────────────────────────────

def build_graph():
    """
    Xây dựng graph với supervisor-worker pattern.
    Option A: Python thuần (không cần LangGraph).
    Flow: supervisor → route → [retrieval | policy_tool | human_review] → synthesis → END
    """
    def run(state: AgentState) -> AgentState:
        start = time.time()

        # Step 1: Supervisor quyết định route
        state = supervisor_node(state)

        # Step 2: Route tới worker phù hợp
        route = route_decision(state)

        if route == "human_review":
            state = human_review_node(state)
            # Sau human approve → retrieval
            state = retrieval_worker_node(state)

        elif route == "policy_tool_worker":
            # policy_tool_worker_node tự gọi retrieval nếu cần
            state = policy_tool_worker_node(state)

        else:
            # Default: retrieval_worker
            state = retrieval_worker_node(state)

        # Step 3: Synthesis luôn chạy cuối
        state = synthesis_worker_node(state)

        state["latency_ms"] = int((time.time() - start) * 1000)
        state["history"].append(
            f"[graph] completed in {state['latency_ms']}ms | "
            f"workers={state['workers_called']} | "
            f"confidence={state.get('confidence', 0):.2f}"
        )
        return state

    return run


# ─────────────────────────────────────────────
# 7. Public API
# ─────────────────────────────────────────────

_graph = build_graph()


def run_graph(task: str) -> AgentState:
    """
    Entry point: nhận câu hỏi, trả về AgentState với full trace.
    """
    state = make_initial_state(task)
    result = _graph(state)
    return result


def save_trace(state: AgentState, output_dir: str = "./artifacts/traces") -> str:
    """Lưu trace ra file JSON."""
    os.makedirs(output_dir, exist_ok=True)
    run_id = state.get("run_id", f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    q_id = state.get("question_id", "")
    suffix = f"_{q_id}" if q_id else ""
    filename = f"{output_dir}/{run_id}{suffix}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return filename


# ─────────────────────────────────────────────
# 8. Manual Test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("Day 09 Lab — Supervisor-Worker Graph (REAL)")
    print("=" * 65)

    test_queries = [
        ("q_test_1", "SLA xử lý ticket P1 là bao lâu?"),
        ("q_test_2", "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?"),
        ("q_test_3", "Ticket P1 lúc 2am. Cần cấp Level 2 access tạm thời cho contractor để fix. Cả hai quy trình là gì?"),
    ]

    for q_id, query in test_queries:
        print(f"\n" + "-"*60)
        print(f"[{q_id}] {query[:70]}")
        result = run_graph(query)
        print(f"  Route    : {result['supervisor_route']}")
        print(f"  Reason   : {result['route_reason']}")
        print(f"  Workers  : {result['workers_called']}")
        print(f"  MCP tools: {[t.get('tool') for t in result.get('mcp_tools_used', [])]}")
        print(f"  Sources  : {result['retrieved_sources']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Latency  : {result['latency_ms']}ms")
        print(f"\n  Answer:\n  {result['final_answer'][:300]}")

        result["question_id"] = q_id
        trace_file = save_trace(result)
        print(f"\n  Trace → {trace_file}")

    print("\n\n[DONE] graph.py test complete!")
