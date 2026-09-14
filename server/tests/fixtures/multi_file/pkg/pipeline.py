from google.adk.agents import SequentialAgent
from .researcher import researcher
from .writer import writer

pipeline = SequentialAgent(
    name="pipeline",
    sub_agents=[researcher, writer],
)
