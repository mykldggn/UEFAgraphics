from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    FRONTEND_URL: str = "http://localhost:5173"
    CACHE_DIR: str = "./cache"
    SOCCERDATA_DIR: str = "./soccerdata_cache"
    API_FOOTBALL_KEY: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
