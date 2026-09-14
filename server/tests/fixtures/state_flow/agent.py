from google.adk.agents import LlmAgent

drafter = LlmAgent(
    name="drafter",
    model="m",
    instruction="Draft it.",
    output_key="draft",
)

editor = LlmAgent(
    name="editor",
    model="m",
    instruction="Edit this draft: {draft}",
    output_key="edited",
)

publisher = LlmAgent(
    name="publisher",
    model="m",
    instruction="Publish this: {edited}. Reference: {draft}",
)

# Consumer of a key nobody produces — no edge should be emitted.
loner = LlmAgent(
    name="loner",
    model="m",
    instruction="Use {ghost} somehow.",
)
