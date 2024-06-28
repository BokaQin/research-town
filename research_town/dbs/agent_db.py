import json
import uuid

from beartype.typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ..utils.paper_collector import get_bert_embedding, neiborhood_search


class AgentProfile(BaseModel):
    pk: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = Field(default=None)
    bio: Optional[str] = Field(default=None)
    collaborators: Optional[List[str]] = Field(default=[])
    institute: Optional[str] = Field(default=None)


class AgentProfileDB(object):
    def __init__(self) -> None:
        self.data: Dict[str, AgentProfile] = {}

    def add(self, agent: AgentProfile) -> None:
        self.data[agent.pk] = agent

    def update(self, agent_pk: str, updates: Dict[str, Optional[str]]) -> bool:
        if agent_pk in self.data:
            for key, value in updates.items():
                if value is not None:
                    setattr(self.data[agent_pk], key, value)
            return True
        return False

    def delete(self, agent_pk: str) -> bool:
        if agent_pk in self.data:
            del self.data[agent_pk]
            return True
        return False

    def get(self, **conditions: Dict[str, Any]) -> List[AgentProfile]:
        result = []
        for agent in self.data.values():
            if all(getattr(agent, key) == value for key, value in conditions.items()):
                result.append(agent)
        return result

    def match(
        self, idea: str, agent_profiles: List[AgentProfile], num: int = 1
    ) -> List[str]:
        idea_embed = get_bert_embedding([idea])
        bio_list = []
        for agent_profile in agent_profiles:
            if agent_profile.bio is not None:
                bio_list.append(agent_profile.bio)
            else:
                bio_list.append('')
        profile_embed = get_bert_embedding(bio_list)
        index_l = neiborhood_search(idea_embed, profile_embed, num).reshape(-1)
        index_all = list(index_l)
        match_pk = []
        for index in index_all:
            match_pk.append(agent_profiles[index].pk)
        return match_pk

    def save_to_file(self, file_name: str) -> None:
        with open(file_name, 'w') as f:
            json.dump(
                {aid: agent.model_dump() for aid, agent in self.data.items()},
                f,
                indent=2,
            )

    def load_from_file(self, file_name: str) -> None:
        with open(file_name, 'r') as f:
            data = json.load(f)
            self.data = {
                aid: AgentProfile(**agent_data) for aid, agent_data in data.items()
            }

    def update_db(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        for date, agents in data.items():
            for agent_data in agents:
                agent = AgentProfile(**agent_data)
                self.add(agent)