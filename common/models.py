from pydantic import BaseModel, Field
import enum
from typing import Optional, Union
import datetime

class Account(BaseModel):
    user_id: str = Field(..., min_length=1)  # primary key, must be non-empty
    username: str = Field(..., min_length=1)  # must be non-empty
    password_hash: str = Field(..., min_length=1)  # must be non-empty
    created_at: Union[str, datetime.datetime] = Field(default_factory=datetime.datetime.now)

# class Portfolio(BaseModel):
#     portfolio_id: str = Field(..., min_length=1)  # primary key, must be non-empty
#     portfolio_name: str = Field(..., min_length=1)  # the name the user gives for the portfolio
#     portfolio_address: str = Field(..., min_length=1)  # the address of the portfolio on AWS S3
#     created_at: Union[str, datetime.datetime] = Field(default_factory=datetime.datetime.now)