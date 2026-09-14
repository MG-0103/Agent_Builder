"""Attribute-chain refs across modules.

- `import pkg.researcher` binds top-level `pkg`; access as `pkg.researcher.researcher`.
- `import pkg.tools_mod as tm` binds `tm` to the full module; access as `tm.search_web`.
"""
import pkg.researcher
import pkg.tools_mod as tm
from google.adk.agents import SequentialAgent, LlmAgent

user = LlmAgent(name="user", model="m", instruction="u", tools=[tm.search_web])

pipeline = SequentialAgent(
    name="pipeline",
    sub_agents=[pkg.researcher.researcher, user],
)
