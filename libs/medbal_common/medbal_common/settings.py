from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+psycopg://medbal:medbal@postgres:5432/medbal"
    REDIS_URL: str = "redis://redis:6379/0"
    MQTT_URL: str = "mqtt://mosquitto:1883"
    SIM_CONTROL_URL: str = "http://sim-control:8100"
    USE_FIXTURES: bool = False
    DEMO_MODE: Literal["live", "record", "replay"] = "live"

    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL_FAST: str = "gemini-3.8-flash"
    LLM_MODEL_SMART: str = "gemini-3.8-flash"

    QPIAI_OPT_URL: str = ""
    QPIAI_OPT_TOKEN: str = ""
    QPIAI_QCLOUD_API_KEY: str = ""
    QPIAI_QCLOUD_BACKEND: str = "QpiAI-QSV-Simulator"
    QPIAI_TIMEOUT_S: int = 20

    QR_HMAC_SECRET: str = ""
    SIM_SEED: int = 42
    SIM_DAY_SECONDS: int = 30
    SIM_START_DATE: str = "2026-11-01"

    @staticmethod
    def _is_set(v: str) -> bool:
        return bool(v) and not v.startswith("<paste-")

    def has_anthropic(self) -> bool:
        return self._is_set(self.ANTHROPIC_API_KEY)

    def has_gemini(self) -> bool:
        return self._is_set(self.GEMINI_API_KEY)

    def has_qpiai_opt(self) -> bool:
        return self._is_set(self.QPIAI_OPT_URL) and self._is_set(self.QPIAI_OPT_TOKEN)

    def has_qcloud(self) -> bool:
        return self._is_set(self.QPIAI_QCLOUD_API_KEY)

    def key_status(self) -> dict[str, str]:
        return {
            "ANTHROPIC_API_KEY": "set" if self.has_anthropic() else "missing",
            "GEMINI_API_KEY": "set" if self.has_gemini() else "missing",
            "QPIAI_OPT_URL": "set" if self._is_set(self.QPIAI_OPT_URL) else "missing",
            "QPIAI_OPT_TOKEN": "set" if self._is_set(self.QPIAI_OPT_TOKEN) else "missing",
            "QPIAI_QCLOUD_API_KEY": "set" if self.has_qcloud() else "missing",
        }


settings = Settings()
