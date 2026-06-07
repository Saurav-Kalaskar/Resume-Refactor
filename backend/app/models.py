from pydantic import BaseModel
from typing import Optional, List

class RefactorRequest(BaseModel):
    job_description: str
    base_resume_tex: Optional[str] = None
    model: Optional[str] = None
    resume_version: Optional[str] = "v1"

class ResumeVersion(BaseModel):
    version: str
    label: str

class ResumeListResponse(BaseModel):
    resumes: List[ResumeVersion]

class RefactorResponse(BaseModel):
    status: str
    message: str
    pdf_base64: Optional[str] = None
    latex_source: str
    bullets_applied: int
    keywords_found: List[str]
    company_name: Optional[str] = None
