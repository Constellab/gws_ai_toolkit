from typing import Literal

# Common status enums
RagDocumentStatus = Literal["DONE", "PENDING", "RUNNING", "ERROR"]
RagProvider = Literal["dify", "ragflow"]

# Mode for the resource to sync with the RAG platform
# - datahub: Sync resources from DataHub
# - tag: Sync resources which have a specific tag
RagResourceSyncMode = Literal["datahub", "tag"]

# Common search methods (intersection of both platforms)
RagSearchMethod = Literal["semantic_search", "keyword_search", "hybrid_search"]

# Common file extensions supported by both platforms
RAG_COMMON_SUPPORTED_EXTENSIONS = ["txt", "pdf", "docx", "doc", "md", "json"]

# Common maximum file size (using the smaller of the two)
RAG_COMMON_MAX_FILE_SIZE_MB = 15
