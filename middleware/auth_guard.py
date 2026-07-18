from agent.state import AgentState

class AuthGuard:
    @staticmethod
    def check_approval(state: AgentState):
        if not state.get("is_approved", False):
            print("Action blocked: Waiting for human approval...")
            return False
        return True

    @staticmethod
    def approve_action(state: AgentState):
        state["is_approved"] = True
        print("Action approved by human.")