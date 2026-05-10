from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Bot(BaseSettings):
    BOT_TOKEN: str
    ADMINS: list[int]
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf8", extra="ignore")

    @field_validator('ADMINS', mode='before')
    def parse_admins(cls, value):
        if isinstance(value, str):
            return [int(x.strip()) for x in value.split(',') if x.strip()]
        return value


class DBSettings(BaseSettings):
    DB_HOST: str
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    DB_PORT: str
    DB_ECHO: bool


    @property
    def postgres_url(self):
       return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

class RedisSettings(BaseSettings):
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf8", extra="ignore")

    # @property
    # def redis_url(self):
    #     return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

# class EmailSettings(BaseSettings):
#     email_host: str
#     email_port: int
#     email_username: str
#     email_password: SecretStr
#
#     model_config = SettingsConfigDict(env_file="lichenid/.env", env_file_encoding="utf8", extra="ignore")


# class S3Settings(BaseSettings):
#     S3_access_key: str
#     S3_url: str
#     S3_secret_key: SecretStr
#     S3_bucket: str
#     base_url: str
#
#     model_config = SettingsConfigDict(env_file="lichenid/.env", env_file_encoding="utf8", extra="ignore")

class Settings(BaseSettings):
    bot: Bot = Bot()
    db_settings: DBSettings = DBSettings()
    # email_settings: EmailSettings = EmailSettings()
    # S3_settings: S3Settings = S3Settings()
    redis_settings: RedisSettings = RedisSettings()
    # templates_dir: str = "/templates"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf8", extra="ignore")


settings = Settings()