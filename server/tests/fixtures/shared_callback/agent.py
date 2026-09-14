from google.adk.agents import LlmAgent


def before(ctx):
    pass


alpha = LlmAgent(name="alpha", model="m", instruction="a", before_agent_callback=before)
beta = LlmAgent(name="beta", model="m", instruction="b", before_agent_callback=before)
