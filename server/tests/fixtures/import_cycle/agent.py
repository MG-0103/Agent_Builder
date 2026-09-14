from google.adk.agents import LlmAgent
from .a import thing

# `thing` never actually defined anywhere — resolver should give up cleanly.
agent = LlmAgent(name="cyc", model="gemini-2.0-flash", instruction="c", sub_agents=[thing])
