from typing import Optional, Type, TypeVar

import reflex as rx

T_STATE = TypeVar("T_STATE", bound=rx.State)


class Utils:

    @staticmethod
    async def get_first_state_of_type(state: rx.State, state_type: Type[T_STATE]) -> Optional[T_STATE]:
        """Get the first state of a specific type from the state hierarchy.

        Args:
            state (rx.State): The current state instance.
            state_type (Type[rx.State]): The type of state to search for.

        Returns:
            Optional[rx.State]: The first found state of the specified type, or None if not found.
        """
        root_state = state.get_root_state()
        sub_states = root_state.get_substates()

        for sub in sub_states:
            if issubclass(sub, state_type):
                return await state.get_state(sub)

        return None
