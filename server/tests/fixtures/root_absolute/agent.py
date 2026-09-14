"""Agent at repo root: no package, fq_module == ''."""
from google.adk.agents import LlmAgent

solo = LlmAgent(name="solo", model="gemini-2.0-flash", instruction="s")
