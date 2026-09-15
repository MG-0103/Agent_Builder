"""Fixture where the root agent only exists via a factory call.

The static parser can't unwrap `build_root()`, so it sees zero agents at
module level. The deeper walker with entry_object='build_root' calls the
function and walks the returned agent's sub_agents + tools.
"""


class _Agent:
    def __init__(self, name, tools=None, sub_agents=None, before_agent_callback=None):
        self.name = name
        self.tools = tools or []
        self.sub_agents = sub_agents or []
        self.before_agent_callback = before_agent_callback


def _search(q):
    return q


def _summarize(text):
    return text


def _on_before(ctx):
    pass


def build_root():
    researcher = _Agent(
        name="researcher",
        tools=[_search, _summarize],
        before_agent_callback=_on_before,
    )
    writer = _Agent(name="writer")
    return _Agent(name="pipeline", sub_agents=[researcher, writer])
