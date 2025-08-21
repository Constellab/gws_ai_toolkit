
import importlib

from gws_ai_toolkit.rag.datahub_dify_app._datahub_dify_app.datahub_app_state import \
    DatahubRagAppState
from gws_ai_toolkit.rag.datahub_dify_app._datahub_dify_app.pages import (
    datahub_app_chat_page, datahub_app_config_page)
from gws_core import DifyService
from gws_core.streamlit import StreamlitRouter

sources: list
params: dict

# Uncomment if you want to hide the Streamlit sidebar toggle and always show the sidebar
# from gws_core.streamlit import StreamlitHelper
# StreamlitHelper.hide_sidebar_toggle()

router = StreamlitRouter.load_from_session()

rag_provider = params.get('rag_provider')
filter_rag_with_user_folders = params.get('filter_rag_with_user_folders')

if filter_rag_with_user_folders and rag_provider == 'ragflow':
    raise Exception(
        "RAGFlow does not support filtering by user folders. Please remove this option in dashboard generation config")

# Initialize the app state
DatahubRagAppState.init(
    chat_credentials_name=params.get('chat_credentials_name'),
    knowledge_base_credentials_name=params.get('knowledge_base_credentials_name'),
    knowledge_base_id=params.get('knowledge_base_id'),
    rag_provider=rag_provider,
    filter_rag_with_user_folders=filter_rag_with_user_folders
)

chat_state = datahub_app_chat_page.DataHubRagAppChatPageState.init(params.get('root_folder_limit'),
                                                                   filter_rag_with_user_folders,
                                                                   chat_id=params.get('chat_id'))

dify_service = DifyService.from_credentials(DatahubRagAppState.get_knowledge_base_credentials())


def _render_chat_page():
    importlib.reload(datahub_app_chat_page)
    datahub_app_chat_page.render_page(chat_state)


def _render_config_page():
    importlib.reload(datahub_app_config_page)
    datahub_app_config_page.render_page()


router.add_page(_render_chat_page, title='Chat page', url_path='chat-page', icon='💬')

if params.get('show_config_page'):
    # Add the config page only if the parameter is set to True
    router.add_page(_render_config_page, title='Config page', url_path='config-page', icon='⚙️')

router.run()
