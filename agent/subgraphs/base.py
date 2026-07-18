from abc import ABC, abstractmethod
from agent.state import AgentState

class BaseAgent(ABC):
    @abstractmethod
    def run(self, state: AgentState):
        pass