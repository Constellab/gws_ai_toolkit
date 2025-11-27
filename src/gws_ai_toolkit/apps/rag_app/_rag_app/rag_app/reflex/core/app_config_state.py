import os
from abc import abstractmethod
from json import dump, load

import reflex as rx
from gws_core import BaseModelDTO, Logger


class AppConfigStateConfig(BaseModelDTO):
    configuration_file_path: str
    chat_app_name: str


class AppConfigState(rx.State, mixin=True):
    """Application configuration management state.

    This state class manages the application-wide configuration system,
    handling loading, saving, and accessing configuration data from JSON files.
    It provides a centralized configuration management system for all app settings.

    Features:
        - JSON file-based configuration storage
        - Dynamic configuration loading with custom loaders
        - Section-based configuration management
        - Type-safe configuration access
        - Automatic serialization and deserialization

    The state uses a loader pattern to determine the configuration file path,
    allowing different deployment scenarios and parameter-based configuration.
    """

    # Required properties
    _config: dict

    _app_config: AppConfigStateConfig

    __sub_class_type__: type["AppConfigState"] | None = None

    @abstractmethod
    async def _get_config(self) -> AppConfigStateConfig:
        pass

    async def get_app_config(self) -> AppConfigStateConfig:
        if not self._app_config:
            self._app_config = await self._get_config()
        return self._app_config

    async def get_config_file_path(self) -> str:
        config = await self.get_app_config()
        return config.configuration_file_path

    async def get_chat_app_name(self) -> str:
        config = await self.get_app_config()
        return config.chat_app_name

    async def config(self) -> dict:
        """Get the current app configuration."""

        if not self._config:
            config_file_path = await self.get_config_file_path()
            if not config_file_path:
                return {}
            self._config = self._load_config_file(config_file_path)

        return self._config

    async def get_config_section(self, key: str, type_: type[BaseModelDTO]) -> BaseModelDTO:
        """Get a specific section of the configuration as a DTO."""
        config = await self.config()
        if key not in config:
            Logger.warning(f"Config section '{key}' not found. Returning empty instance of {type_.__name__}.")
            return type_()
        section_data = config.get(key, {})
        return type_(**section_data)

    async def update_config(self, new_config: dict) -> None:
        """Update the app configuration."""
        self._config = new_config

        config_file_path = await self.get_config_file_path()
        self._save_config_file(new_config, config_file_path)

    async def update_config_section(self, key: str, new_data: BaseModelDTO):
        """Update a specific section of the configuration."""
        config = await self.config()
        config[key] = new_data.to_json_dict()
        await self.update_config(config)

        return rx.toast.success("Configuration updated successfully.")

    def _load_config_file(self, config_file_path: str) -> dict:
        if not config_file_path or not os.path.exists(config_file_path):
            return {}

        try:
            with open(config_file_path, encoding="utf-8") as file:
                return load(file)
        except Exception as e:
            Logger.error(f"Error reading config file: {e}")
            return {}

    def _save_config_file(self, config: dict, config_file_path: str) -> None:
        if not config:
            return

        if not config_file_path:
            raise ValueError("Config file path is not set.")

        try:
            with open(config_file_path, "w", encoding="utf-8") as file:
                dump(config, file)
        except Exception as e:
            raise ValueError(f"Error writing config file: {e}")

    @staticmethod
    async def get_instance(state: rx.State) -> "AppConfigState":
        """Get the AppConfigState instance from any state."""

        if AppConfigState.__sub_class_type__ is None:
            raise Exception(
                "AppConfigState subclass not registered. You must call "
                "set_config_state_class_type() during app initialization to register "
                "your custom AppConfigState subclass."
            )

        return await state.get_state(AppConfigState.__sub_class_type__)

    @staticmethod
    def set_config_state_class_type(state_type: type["AppConfigState"]):
        """Set the AppConfigState subclass type for the app.

        This method should be called during app initialization to register
        the custom AppConfigState subclass.

        Args:
            state_type (Type[AppConfigState]): The subclass of AppConfigState to register.
        """
        AppConfigState.__sub_class_type__ = state_type
