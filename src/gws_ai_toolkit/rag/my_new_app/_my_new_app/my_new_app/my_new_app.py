
import reflex as rx
from gws_reflex_base import (add_unauthorized_page, get_theme,
                             render_main_container)

from gws_ai_toolkit._reflex import ChatStateBase

app = rx.App(
    theme=get_theme()
)


# Declare the page and init the main state
@rx.page()
def index():
    # Render the main container with the app content.
    # The content will be displayed once the state is initialized.
    # If the state is not initialized, a loading spinner will be shown.
    return render_main_container(rx.box(
        rx.heading("Reflex app", font_size="2em"),

    ))


# Add the unauthorized page to the app.
# This page will be displayed if the user is not authenticated
add_unauthorized_page(app)
