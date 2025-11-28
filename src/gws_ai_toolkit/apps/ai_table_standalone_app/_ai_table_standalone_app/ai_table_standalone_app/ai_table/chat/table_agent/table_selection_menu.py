import reflex as rx
from gws_ai_toolkit.core.excel_file import ExcelFileDTO

from ...ai_table_data_state import AiTableDataState
from .ai_table_agent_chat_state import AiTableAgentChatState


def _item(table_item: ExcelFileDTO) -> rx.Component:
    return rx.cond(
        table_item.sheets,
        rx.menu.sub(
            rx.menu.sub_trigger(table_item.name),
            rx.menu.sub_content(
                rx.foreach(
                    table_item.sheets,
                    lambda sheet: rx.menu.item(
                        sheet,
                        on_click=lambda: AiTableAgentChatState.add_table(table_item.id, sheet),
                    ),
                ),
            ),
        ),
        rx.menu.item(
            table_item.name,
            on_click=lambda: AiTableAgentChatState.add_table(table_item.id, ""),
        ),
    )


def table_selection_menu():
    """
    Menu for selecting tables and sheets using AiTableDataState.all_table_items.
    If a table has sheets, show as submenu; otherwise, show as direct item.
    """
    return rx.menu.root(
        rx.menu.trigger(
            rx.button(rx.icon("plus", size=16), variant="soft", size="1"),
        ),
        rx.menu.content(
            rx.foreach(
                AiTableDataState.all_table_items,
                _item,
            ),
        ),
    )
