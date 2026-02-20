from typing import List, Optional
from pydantic import BaseModel

class VoiceOption(BaseModel):
    id: str
    description: str
    sample_url: Optional[str] = None

class ModelOption(BaseModel):
    id: str
    label: str
    cost: float

class LanguageOption(BaseModel):
    id: str
    label: str

class ConfigOptionsResponse(BaseModel):
    voices: List[VoiceOption]
    models: List[ModelOption]
    languages: List[LanguageOption]
