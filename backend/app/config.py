from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  model_config = SettingsConfigDict(env_file=".env", extra="ignore")

  database_url: str = "sqlite:///./msr_map.db"
  secret_key: str = "dev-secret-key-change-in-production"
  jwt_algorithm: str = "HS256"
  jwt_expire_minutes: int = 1440
  hold_deadman_seconds: int = 120
  cache_hold_required_seconds: int = 600  # этап 3: 10 минут удержания схрона
  cors_origins: str = "http://localhost:5173,https://preshevkadastr.ru"
  public_app_url: str = "https://preshevkadastr.ru"

  @property
  def cors_origins_list(self) -> list[str]:
    return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
