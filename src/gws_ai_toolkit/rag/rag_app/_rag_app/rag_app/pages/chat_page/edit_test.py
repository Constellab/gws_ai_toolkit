import reflex as rx


class MainState(rx.State):

    @rx.var
    def initial_value(self) -> int:
        return 7


class ReusableCounter(rx.ComponentState):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1

    @rx.event
    def decrement(self):
        self.count -= 1

    @classmethod
    def get_component(cls, **props):

        initial_value = props.pop("initial_value", None)
        cls.__fields__["count"].default = initial_value
        return rx.hstack(
            rx.button("Decrement", on_click=cls.decrement),
            rx.text(cls.count),
            rx.button("Increment", on_click=cls.increment),
            **props
        )


reusable_counter = ReusableCounter.create


def render():
    return reusable_counter(initial_value=MainState.initial_value)
