from pydantic import BaseModel
from typing import List, Optional

# Used for returning JWT to frontend
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# Used for representing Google Drive files
class DriveFile(BaseModel):
    id: str
    name: str
    mimeType: str

# When user selects files to import
class ImportRequest(BaseModel):
    file_ids: List[str]

# Question input for QA endpoint
class QuestionRequest(BaseModel):
    question: str
    k: Optional[int] = 4
