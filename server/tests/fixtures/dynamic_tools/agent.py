from google.adk.agents import LlmAgent


def search(q: str) -> str: return ""
def summarize(t: str) -> str: return ""
def translate(t: str) -> str: return ""
def fetch(u: str) -> str: return ""


def build_tools():
    return [search, summarize]


extra_tools = [translate]

# 1) Variable holds literal list.
var_tools = [search, fetch]
via_var = LlmAgent(name="via_var", model="m", instruction="v", tools=var_tools)

# 2) Function call returning literal list.
via_fn = LlmAgent(name="via_fn", model="m", instruction="v", tools=build_tools())

# 3) Concatenation of two resolvable expressions.
via_concat = LlmAgent(name="via_concat", model="m", instruction="v", tools=build_tools() + extra_tools)


def dyn(): return list(some_registry)  # unresolvable — not a list literal


via_dyn = LlmAgent(name="via_dyn", model="m", instruction="v", tools=dyn())
