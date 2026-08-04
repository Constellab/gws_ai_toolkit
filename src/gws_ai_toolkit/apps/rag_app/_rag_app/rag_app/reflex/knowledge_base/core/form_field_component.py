"""The labelled form field the knowledge-base forms share.

Both the create dialog and the add-document dialog ask for a handful of values with a label and, where
the value decides something the user cannot see, a line explaining what. One helper, so the two forms
cannot drift apart in spacing or in where the hint sits.
"""

import reflex as rx


def form_field(label: str, field: rx.Component, hint: str | None = None) -> rx.Component:
    """A labelled form field, with an optional line explaining what it decides.

    :param label: the field's label
    :param field: the input itself
    :param hint: one line of explanation shown under the input
    """
    return rx.vstack(
        rx.text(label, size="2", weight="medium"),
        field,
        rx.text(hint, size="1", color="var(--gray-10)") if hint else rx.fragment(),
        spacing="1",
        width="100%",
    )
