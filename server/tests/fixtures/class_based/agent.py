from google.adk.agents import LlmAgent, SequentialAgent


def search(q: str) -> str: return ""
def summarize(t: str) -> str: return ""


def before(ctx): pass


class Researcher(LlmAgent):
    def __init__(self, **kw):
        super().__init__(
            name="researcher",
            model="m",
            instruction="Search {seed}.",
            tools=[search, summarize],
            output_key="notes",
            before_agent_callback=before,
            **kw,
        )


class Writer(LlmAgent):
    def __init__(self):
        super().__init__(
            name="writer",
            model="m",
            instruction="Compose from {notes}.",
        )


r = Researcher()
w = Writer()
pipeline = SequentialAgent(name="pipeline", sub_agents=[r, w])
