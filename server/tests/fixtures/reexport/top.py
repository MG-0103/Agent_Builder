from google.adk.agents import SequentialAgent
from pkg import researcher

pipeline = SequentialAgent(name="pipeline", sub_agents=[researcher])
