from google.adk.agents import BaseAgent, LlmAgent


class Reviewer(LlmAgent):
    pass


class DeepReviewer(Reviewer):
    """Transitive: DeepReviewer -> Reviewer -> LlmAgent."""
    pass


class MyThing(BaseAgent):
    def __init__(self, name):
        super().__init__(name=name)


r = Reviewer(name="r", model="m", instruction="x")
d = DeepReviewer(name="d", model="m", instruction="x")
c = MyThing(name="c")
