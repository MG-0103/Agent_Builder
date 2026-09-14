"""Minimal ADK fixture. Not runnable — parsed statically only."""
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool, AgentTool


def search_web(query: str) -> str:
    return ""


def summarize(text: str) -> str:
    return ""


def before_agent(ctx):
    pass


researcher = LlmAgent(
    name="researcher",
    model="gemini-2.0-flash",
    instruction="Research the topic.",
    tools=[search_web, FunctionTool(summarize)],
    before_agent_callback=before_agent,
)

writer = LlmAgent(
    name="writer",
    model="gemini-2.0-flash",
    instruction="Write from the research.",
    tools=[AgentTool(agent=researcher)],
)

pipeline = SequentialAgent(
    name="pipeline",
    sub_agents=[researcher, writer],
)
