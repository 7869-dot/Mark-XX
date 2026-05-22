from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    # 500-char ceiling matches the product spec for agent broadcast posts.
    content: str = Field(..., min_length=1, max_length=500)
