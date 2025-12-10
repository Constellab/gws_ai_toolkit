from gws_core import BrickMigration, SqlMigrator, Version, brick_migration

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.chat.chat_message_source_model import ChatMessageSourceModel


@brick_migration(
    "0.1.8",
    short_description="Migrate source from multiple chunks to single chunks",
    db_manager=AiToolkitDbManager.get_instance(),
)
class Migration012(BrickMigration):
    @classmethod
    def migrate(cls, sql_migrator: SqlMigrator, from_version: Version, to_version: Version) -> None:
        """Migrate sources from old structure (one source with multiple chunks) to new structure (one source per chunk)."""

        sql_migrator.rename_column_if_exists(
            ChatMessageSourceModel,
            "chunks",
            "chunk",
        )
        sql_migrator.migrate()

        sources: list[ChatMessageSourceModel] = list(ChatMessageSourceModel.select())

        for source in sources:
            if source.chunk is None:
                continue

            json_chunks = source.chunk
            if isinstance(json_chunks, dict):
                # Already single chunk (new format), skip
                continue

            if isinstance(json_chunks, list) and len(json_chunks) > 0:
                # Old format: list of chunks
                # Keep the first chunk in the existing source
                first_chunk = json_chunks[0]
                source.chunk = first_chunk
                source.save(skip_hook=True)

                # Create new sources for the remaining chunks
                for chunk in json_chunks[1:]:
                    new_source = ChatMessageSourceModel()
                    new_source.message = source.message
                    new_source.document_id = source.document_id
                    new_source.document_name = source.document_name
                    # Update score to the chunk's score if available
                    new_source.score = chunk.get("score", source.score)
                    new_source.chunk = chunk
                    new_source.save(skip_hook=True)
            elif isinstance(json_chunks, list) and len(json_chunks) == 0:
                # Empty list, set to None
                source.chunk = None
                source.save()
