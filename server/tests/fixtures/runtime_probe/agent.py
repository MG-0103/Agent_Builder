"""Duck-typed agent fixture (no google-adk dep).

Runtime probe walks module-level objects with `.name` + `.tools`/`.sub_agents`.
"""


class LlmAgent:
    def __init__(self, name, tools=None, sub_agents=None):
        self.name = name
        self.tools = tools or []
        self.sub_agents = sub_agents or []


class SequentialAgent:
    def __init__(self, name, sub_agents=None):
        self.name = name
        self.sub_agents = sub_agents or []


def search(q: str) -> str: return ""
def summarize(t: str) -> str: return ""

# Only visible at runtime — parent script builds this dynamically at import time.
def _dyn():
    return [search, summarize]


researcher = LlmAgent(name="researcher", tools=_dyn())
writer = LlmAgent(name="writer")
pipeline = SequentialAgent(name="pipeline", sub_agents=[researcher, writer])
