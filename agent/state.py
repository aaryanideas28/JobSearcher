from typing import Annotated, TypedDict, List, Optional
from pydantic import BaseModel, Field
import operator

class JobPosting(BaseModel):
    id: str
    title: str
    company: str
    description: str
    url: str
    status: str = "discovered"

class ApplicationDraft(BaseModel):
    job_id: str
    cover_letter: str
    resume_version: str

class AgentState(TypedDict):
    messages: Annotated[List[str], operator.add]
    jobs: Annotated[List[JobPosting], operator.add]
    current_draft: Optional[ApplicationDraft]
    is_approved: bool = False