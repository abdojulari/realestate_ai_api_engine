from pydantic import BaseModel

class Prompt(BaseModel):
    prompt: str
    email: str = None
    frequency: int = None  # in hours
