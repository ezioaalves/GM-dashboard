import os
from types import SimpleNamespace
from uuid import uuid4

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://kaihou_gm:kaihou_gm_dev@127.0.0.1:54329/kaihou_gm")

from gm_dashboard.campaign.ideas.service import IDEA_TRANSITIONS, IdeaService, InvalidIdeaTransition


class Repository:
    def __init__(self, idea): self.idea = idea
    def get(self, _db, _idea_id): return self.idea


class Database:
    def __init__(self): self.commits = 0
    def commit(self): self.commits += 1
    def refresh(self, _idea): pass


def test_transition_policy_is_complete_and_idempotent():
    assert IDEA_TRANSITIONS == {"captured": ("captured", "triaged", "discarded"), "triaged": ("triaged", "captured", "promoted", "discarded"), "promoted": ("promoted", "triaged"), "discarded": ("discarded", "captured")}
    idea = SimpleNamespace(state="triaged")
    assert IdeaService(Repository(idea)).update(Database(), uuid4(), {"state": "triaged"}) is idea


def test_transition_policy_rejects_invalid_moves_before_writing():
    idea = SimpleNamespace(state="captured")
    db = Database()
    with pytest.raises(InvalidIdeaTransition) as error:
        IdeaService(Repository(idea)).update(db, uuid4(), {"state": "promoted"})
    assert error.value.allowed_states == ("captured", "triaged", "discarded")
    assert db.commits == 0
