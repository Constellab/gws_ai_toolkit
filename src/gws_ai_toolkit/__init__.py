# Imported for its side effect: importing the module is what registers the
# ``POST /brick/gws_ai_toolkit/chat/ask`` route with ``ApiRegistry``, and nothing else in the brick
# imports it (the route is reached over HTTP, never called directly from Python).
from .api.knowledge_base_api_controller import knowledge_base_api as knowledge_base_api
from .apps.rag_app.generate_knowledge_base_app import GenerateKnowledgeBaseApp
from .core.agents.agent_events import (
    BaseFunctionAgentEvent,
    CodeEvent,
    CreateSubAgent,
    ErrorEvent,
    FunctionCallEvent,
    FunctionErrorEvent,
    FunctionEventBase,
    FunctionSuccessEvent,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseEvent,
    ResponseFullTextEvent,
    SubAgentSuccess,
    TextDeltaEvent,
    UserQueryEventBase,
    UserQueryTextEvent,
)
from .core.agents.agent_stream_adapter import AgentStreamAdapter
from .core.agents.ai_model_factory import AiModelFactory
from .core.agents.base_pydantic_agent_ai import AgentToolSpec, BasePydanticAgentAi
from .core.agents.env_agent_ai import EnvAgentAi
from .core.agents.env_agent_ai_events import (
    EnvFileGeneratedEvent,
    EnvInstallationStartedEvent,
    EnvInstallationSuccessEvent,
)
from .core.agents.env_generator_ai import CondaEnvGeneratorAi, PipEnvGeneratorAi
from .core.agents.table.multi_table_agent_ai import MultiTableAgentAi, MultiTableTransformConfig
from .core.agents.table.multi_table_agent_ai_events import MultiTableTransformEvent
from .core.agents.table.plotly_agent_ai import PlotlyAgentAi
from .core.agents.table.table_agent_ai import (
    PlotRequestConfig,
    TableAgentAi,
    TransformRequestConfig,
)
from .core.agents.table.table_agent_event_base import UserQueryMultiTablesEvent, UserQueryTableEvent
from .core.agents.table.table_transform_agent_ai import TableTransformAgentAi, TableTransformConfig
from .core.agents.table.table_transform_agent_ai_events import TableTransformEvent
from .core.community_dto import BrickDocumentationDTO
from .core.excel_file import ExcelFile
from .core.utils import Utils
from .models.chat.chat_conversation import ChatConversation
from .models.chat.chat_conversation_service import ChatConversationService
from .models.chat.chat_message_model import ChatMessageModel
from .models.chat.conversation.base_chat_conversation import (
    BaseChatConversation,
    BaseChatConversationConfig,
)
from .models.chat.message.chat_message_base import ChatMessageBase
from .models.chat.message.chat_message_code import ChatMessageCode
from .models.chat.message.chat_message_error import (
    ChatMessageError,
)
from .models.chat.message.chat_message_hint import (
    ChatMessageHint,
)
from .models.chat.message.chat_message_image import ChatMessageImage
from .models.chat.message.chat_message_plotly import ChatMessagePlotly
from .models.chat.message.chat_message_source import (
    ChatMessageSource,
    ChatMessageSourceFront,
    RagChatSourceFront,
)
from .models.chat.message.chat_message_streaming import ChatMessageStreaming
from .models.chat.message.chat_message_table import ChatMessageTable
from .models.chat.message.chat_message_text import (
    ChatMessageText,
)
from .models.chat.message.chat_message_types import (
    ChatMessage,
    ChatMessageFront,
)
from .models.chat.message.chat_user_message import (
    ChatUserMessageText,
)

# Importing the knowledge-base models is what registers their tables: gws_core discovers tables by
# walking Model subclasses, so a model nothing imports is a table that is never created.
from .models.knowledge_base.embedding_manifest_model import EmbeddingManifestModel
from .models.knowledge_base.knowledge_base import KnowledgeBase
from .models.knowledge_base.knowledge_base_document import KnowledgeBaseDocument
from .models.knowledge_base.knowledge_base_dto import (
    DocumentIndexStatus,
    ImportedDocumentDTO,
    ImportReport,
    ImportSkipReason,
    KnowledgeBaseDocumentDTO,
    KnowledgeBaseDTO,
    SaveKnowledgeBaseDTO,
    SkippedDocumentDTO,
)
from .models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from .models.knowledge_base.rag_chat_profile import RagChatProfile
from .models.knowledge_base.rag_chat_profile_dto import (
    RagChatProfileDTO,
    SaveRagChatProfileDTO,
)
from .models.knowledge_base.rag_chat_profile_service import RagChatProfileService
from .rag.common.rag_models import (
    RagChatSource,
    RagChatSourceChunk,
)
from .rag.common.rag_resource import RagResource

# The document-source seam is a cross-brick extension point: another brick registers its own
# provider at load time and must be able to reach these with a top-level import.
from .rag.knowledge_base.sources.knowledge_base_source import (
    DOCUMENT_REJECTION_ERRORS,
    DocumentSourceOperationNotSupportedError,
    KnowledgeBaseDocumentSource,
    KnowledgeBaseDocumentSourceRegistry,
    SourceDocumentCandidate,
    SourceFetchResult,
    SourceOpenAction,
    SourceOpenActionType,
    UnknownDocumentSourceError,
)

# Imported for its side effect as much as for the name: importing the module is what registers the
# ``resource`` provider, and nothing else in the brick imports it (the knowledge-base layer addresses
# providers by source type, never by class).
from .rag.knowledge_base.sources.resource_source import (
    RESOURCE_SOURCE_TYPE,
    ResourceDocumentSource,
)
from .stats.ai_table_relation_stats import AiTableRelationStats
from .stats.ai_table_stats_base import AiTableStatsBase
from .stats.ai_table_stats_class import AiTableStats
from .stats.ai_table_stats_plots import AiTableStatsPlots
from .stats.ai_table_stats_tests import AiTableStatsTests
from .stats.ai_table_stats_tests_pairwise import AiTableStatsTestsPairWise
from .stats.ai_table_stats_type import (
    AiTableStatsResultList,
    AiTableStatsResults,
    AnovaTestDetails,
    BaseTestDetails,
    BenjaminiHochbergTestDetails,
    BonferroniTestDetails,
    ChiSquaredAdjustmentTestDetails,
    ChiSquaredIndependenceTestDetails,
    CorrelationPairwiseDetails,
    DunnTestDetails,
    FriedmanTestDetails,
    HolmTestDetails,
    HomogeneityTestDetails,
    McNemarTestDetails,
    MultiGroupNonParametricTestDetails,
    NormalitySummaryTestDetails,
    NormalityTestDetails,
    PairedNonParametricTestDetails,
    PairwiseComparisonResult,
    ScheffeTestDetails,
    StudentTTestIndependentDetails,
    StudentTTestPairedDetails,
    StudentTTestPairwiseDetails,
    TukeyHSDTestDetails,
    TwoGroupNonParametricTestDetails,
)
from .tasks.download_bricks_documentation import DownloadBricksDocumentation
from .tasks.download_community_stories import DownloadCommunityStories
from .tasks.table_subtable_selector import TableSubtableSelector

__all__ = [
    # Core utilities
    "ExcelFile",
    "Utils",
    "BrickDocumentationDTO",
    # Apps
    "GenerateKnowledgeBaseApp",
    # Rag
    "RagResource",
    "RagChatSourceChunk",
    "RagChatSource",
    # Agents
    "AgentStreamAdapter",
    "AgentToolSpec",
    "AiModelFactory",
    "BasePydanticAgentAi",
    "CodeEvent",
    "CreateSubAgent",
    "ErrorEvent",
    "FunctionCallEvent",
    "FunctionErrorEvent",
    "FunctionEventBase",
    "FunctionSuccessEvent",
    "BaseFunctionAgentEvent",
    "ResponseCompletedEvent",
    "ResponseCreatedEvent",
    "ResponseEvent",
    "ResponseFullTextEvent",
    "TextDeltaEvent",
    "UserQueryEventBase",
    "UserQueryTextEvent",
    "EnvAgentAi",
    "EnvFileGeneratedEvent",
    "EnvInstallationStartedEvent",
    "EnvInstallationSuccessEvent",
    "CondaEnvGeneratorAi",
    "PipEnvGeneratorAi",
    "MultiTableAgentAi",
    "MultiTableTransformConfig",
    "MultiTableTransformEvent",
    "PlotlyAgentAi",
    "TableAgentAi",
    "PlotRequestConfig",
    "TransformRequestConfig",
    "SubAgentSuccess",
    "UserQueryMultiTablesEvent",
    "UserQueryTableEvent",
    "TableTransformAgentAi",
    "TableTransformConfig",
    "TableTransformEvent",
    # Models
    "ChatMessageModel",
    "ChatConversationService",
    "ChatConversation",
    # Models > chat conversation
    "BaseChatConversation",
    "BaseChatConversationConfig",
    # Models > chat messages
    "ChatMessage",
    "ChatMessageBase",
    "ChatMessageText",
    "ChatMessageError",
    "ChatMessageHint",
    "ChatUserMessageText",
    "ChatMessageCode",
    "ChatMessageImage",
    "ChatMessagePlotly",
    "ChatMessageTable",
    "ChatMessageStreaming",
    "ChatMessageFront",
    "ChatMessageSource",
    "ChatMessageSourceFront",
    "RagChatSourceFront",
    # Models > knowledge base
    "KnowledgeBase",
    "KnowledgeBaseDocument",
    "KnowledgeBaseService",
    "EmbeddingManifestModel",
    "KnowledgeBaseDTO",
    "KnowledgeBaseDocumentDTO",
    "SaveKnowledgeBaseDTO",
    "DocumentIndexStatus",
    "ImportReport",
    "ImportedDocumentDTO",
    "SkippedDocumentDTO",
    "ImportSkipReason",
    # Models > chat profile
    "RagChatProfile",
    "RagChatProfileService",
    "RagChatProfileDTO",
    "SaveRagChatProfileDTO",
    # Rag > knowledge base document sources
    "KnowledgeBaseDocumentSource",
    "KnowledgeBaseDocumentSourceRegistry",
    "SourceFetchResult",
    "SourceDocumentCandidate",
    "SourceOpenAction",
    "SourceOpenActionType",
    "UnknownDocumentSourceError",
    "DocumentSourceOperationNotSupportedError",
    "DOCUMENT_REJECTION_ERRORS",
    "ResourceDocumentSource",
    "RESOURCE_SOURCE_TYPE",
    # Stats
    "AiTableStatsBase",
    "AiTableStats",
    "AiTableRelationStats",
    "AiTableStatsTests",
    "AiTableStatsTestsPairWise",
    "AiTableStatsPlots",
    "AiTableStatsResults",
    "AiTableStatsResultList",
    "BaseTestDetails",
    "NormalityTestDetails",
    "NormalitySummaryTestDetails",
    "HomogeneityTestDetails",
    "ChiSquaredAdjustmentTestDetails",
    "ChiSquaredIndependenceTestDetails",
    "McNemarTestDetails",
    "StudentTTestIndependentDetails",
    "StudentTTestPairedDetails",
    "StudentTTestPairwiseDetails",
    "AnovaTestDetails",
    "TwoGroupNonParametricTestDetails",
    "PairedNonParametricTestDetails",
    "MultiGroupNonParametricTestDetails",
    "FriedmanTestDetails",
    "TukeyHSDTestDetails",
    "DunnTestDetails",
    "BonferroniTestDetails",
    "ScheffeTestDetails",
    "BenjaminiHochbergTestDetails",
    "HolmTestDetails",
    "CorrelationPairwiseDetails",
    "PairwiseComparisonResult",
    # Tasks
    "DownloadBricksDocumentation",
    "DownloadCommunityStories",
    "TableSubtableSelector",
]
