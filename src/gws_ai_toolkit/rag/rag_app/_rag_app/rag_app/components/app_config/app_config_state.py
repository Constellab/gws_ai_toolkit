import os
from json import dump, load
from typing import Awaitable, Callable, Type

import reflex as rx
from gws_core import BaseModelDTO
from gws_reflex_main import ReflexMainState


class AppConfigState(rx.State):
    """State class for managing the app configuration.
    And it stores the configuration in a json file.
    """

    # Required properties
    _config: dict

    _config_file_path: str = '/lab/user/bricks/gws_ai_toolkit/src/gws_ai_toolkit/rag/rag_app/_rag_app/app_config.json'

    _loader: Callable[[rx.State], Awaitable[str]] = None

    @classmethod
    def set_loader(cls, loader: Callable[[rx.State], Awaitable[str]]) -> None:
        """Set the loader function to get the path of the config file."""
        cls._loader = loader

    @classmethod
    def set_loader_from_param(cls, param_name: str) -> None:
        """Set the loader function to get the config file path from a parameter."""
        async def loader(state: 'AppConfigState'):
            base_state = await state.get_state(ReflexMainState)
            return await base_state.get_param(param_name)

        cls._loader = loader

    @rx.var()
    async def config_file_path(self) -> str:
        """Get the configuration file path."""
        if not self._config_file_path:
            if not AppConfigState._loader:
                raise ValueError("Loader function is not set. Please call AppConfigState.set_loader")
            self._config_file_path = await AppConfigState._loader(self)

        return self._config_file_path

    async def config(self) -> dict:
        """Get the current app configuration."""

        if not self._config:
            config_file_path = await self.config_file_path
            self._config = self._load_config_file(config_file_path)

        return self._config

    async def get_config_section(self, key: str, type_: Type[BaseModelDTO]) -> BaseModelDTO:
        """Get a specific section of the configuration as a DTO."""
        config = await self.config()
        section_data = config.get(key, {})
        return type_(**section_data)

    async def update_config(self, new_config: dict) -> None:
        """Update the app configuration."""
        self._config = new_config

        config_file_path = await self.config_file_path
        self._save_config_file(new_config, config_file_path)

    async def update_config_section(self, key: str, new_data: BaseModelDTO):
        """Update a specific section of the configuration."""
        config = await self.config()
        config[key] = new_data.to_json_dict()
        await self.update_config(config)

        return rx.toast.success("Configuration updated successfully.")

    def _load_config_file(self, config_file_path: str) -> dict:
        if not os.path.exists(config_file_path):
            return {}

        try:
            with open(config_file_path, 'r', encoding='utf-8') as file:
                return load(file)
        except Exception as e:
            raise ValueError(f"Error reading config file: {e}")

    def _save_config_file(self, config: dict, config_file_path: str) -> None:
        if not config:
            return

        try:
            with open(config_file_path, 'w', encoding='utf-8') as file:
                dump(config, file)
        except Exception as e:
            raise ValueError(f"Error writing config file: {e}")
