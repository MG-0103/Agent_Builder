from google.adk.agents import LlmAgent


class MyLlmCustom(LlmAgent):
    def __init__(self, **kw):
        super().__init__(model="gemini-1.5", instruction="be nice", **kw)
