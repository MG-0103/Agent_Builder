"""Fixture exercising enriched-meta extraction for the auto-probe:
docstrings + parameter annotations + return annotations on tools,
and `description` kwarg on agents."""
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool


def check_balance(account_id: str) -> float:
    """Return the current balance for the given account.

    Args:
        account_id: opaque account identifier.

    Returns:
        Current balance in USD.
    """
    return 0.0


async def send_email(to: str, subject: str, body: str = "") -> bool:
    """Send an email. Returns True on success."""
    return True


refund_agent = LlmAgent(
    name="refund_agent",
    model="gemini-2.0-flash",
    description="Handles refund requests. Invoke when the user asks about "
                "cancelling a charge or requesting money back.",
    instruction="You process refunds. Verify the account, then issue the refund.",
    tools=[check_balance, FunctionTool(send_email)],
)
