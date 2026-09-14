"""ADK graph-API workflow.

Linear + conditional branch. Parser should emit graph_edges between agents.
"""
from google.adk.agents import LlmAgent
from google.adk.workflows import Graph


def route(state) -> str:
    return "approved" if state.get("ok") else "rejected"


planner = LlmAgent(name="planner", model="m", instruction="plan")
approver = LlmAgent(name="approver", model="m", instruction="approve")
rejector = LlmAgent(name="rejector", model="m", instruction="reject")
publisher = LlmAgent(name="publisher", model="m", instruction="publish")

g = Graph()
g.add_node("plan", planner)
g.add_node("approve", approver)
g.add_node("reject", rejector)
g.add_node("publish", publisher)

g.set_entry_point("plan")
g.add_edge("plan", "approve")
g.add_conditional_edges("approve", route, {"approved": "publish", "rejected": "reject"})
