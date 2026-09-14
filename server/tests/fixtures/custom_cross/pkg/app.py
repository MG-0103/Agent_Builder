from .base import Reviewer


class DeepReviewer(Reviewer):
    """Base defined in another module."""


r = Reviewer(name="r", model="m", instruction="x")
d = DeepReviewer(name="d", model="m", instruction="x")
