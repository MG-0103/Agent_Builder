from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool
from .researcher import researcher

writer = LlmAgent(
    name="writer",
    model="gemini-2.0-flash",
    instruction="Write.",
    tools=[AgentTool(agent=researcher)],
)
