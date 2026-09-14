from google.adk.agents import LlmAgent as A, SequentialAgent as Seq

alpha = A(name="alpha", model="gemini-2.0-flash", instruction="a")
beta = A(name="beta", model="gemini-2.0-flash", instruction="b")
pipeline = Seq(name="pipeline", sub_agents=[alpha, beta])
