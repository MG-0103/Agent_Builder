from google.adk.agents import LlmAgent
from .tools import search_web, summarize


def before_agent(ctx):
    pass


researcher = LlmAgent(
    name="researcher",
    model="gemini-2.0-flash",
    instruction="Research.",
    tools=[search_web, summarize],
    before_agent_callback=before_agent,
)
