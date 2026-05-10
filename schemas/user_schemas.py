from pydantic import BaseModel, Field, EmailStr, ConfigDict


class TgID(BaseModel):
    tg_id: int

    model_config = ConfigDict(from_attributes=True)

class CreateUser(TgID):

    firstname: str | None = None
    lastname: str | None = None
    username: str | None = None
    language: str | None = None
    is_registered: bool = None

class UserEmail(BaseModel):
    email: EmailStr

class Nickname(BaseModel):
    nickname: str = Field(..., min_length=3, max_length=30)



class RegisterUser(TgID, UserEmail, Nickname):
    pass

class FindUserReturnData(RegisterUser):
    pass


class OneUserResult(BaseModel):
    username: str
    result: int






