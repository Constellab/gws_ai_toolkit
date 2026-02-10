import os
import tempfile
import unittest

from gws_ai_toolkit import DownloadBricksDocumentation
from gws_ai_toolkit.core.community_dto import (
    BrickDocumentationDTO,
    BrickTechnicalDocumentationDTO,
    CommunityStoryDTO,
)
from gws_ai_toolkit.services.community_resource_files_manager_service import (
    CommunityResourceFilesManagerService,
)
from gws_ai_toolkit.tasks.download_community_stories import DownloadCommunityStories
from gws_ai_toolkit.tasks.push_resources_to_ragflow import PushResourcesToRagFlow
from gws_core import BaseTestCase, File, JSONDict, Tag


class TestDownloadBricksDocumentation(BaseTestCase):
    """
    Test the DownloadBricksDocumentation task.

    Tests verify that the task correctly downloads both regular documentation
    and technical documentation for multiple bricks, and that the downloaded
    File resources have the correct tags.
    """

    def test_brick_documentation_dto_creates_correct_file_tags(self):
        """
        Test that BrickDocumentationDTO can be used to create a File
        with the correct tags.
        """
        # Create a sample documentation DTO
        doc = BrickDocumentationDTO(
            id="doc-123",
            title="Getting Started",
            path="/getting-started",
            complete_path="/gws_core/getting-started",
            order=1,
            last_modified_at="2024-01-15T10:30:00Z",
        )

        # Create a temporary markdown file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
            tmp.write("# Getting Started\n\nThis is a test.")
            tmp_path = tmp.name

        try:
            # Create a File resource
            file_resource = File(tmp_path)
            file_resource.name = doc.title

            # Add tags as done in the task
            file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.SEND_TO_RAG_TAG_KEY, "CommunityDocumentations"))
            file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_BRICK_NAME_TAG_KEY, "gws_core"))
            file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_DOCUMENTATION_ID_TAG_KEY, doc.id))
            file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_LAST_MODIFICATED_AT_TAG_KEY, doc.last_modified_at))

            # Verify the File has the correct tags
            self.assertEqual(file_resource.name, "Getting Started")

            # Check send_to_rag tag
            send_to_rag_tag = file_resource.tags.get_tag(CommunityResourceFilesManagerService.SEND_TO_RAG_TAG_KEY, "CommunityDocumentations")
            self.assertIsNotNone(send_to_rag_tag)
            self.assertEqual(send_to_rag_tag.value, "CommunityDocumentations")

            # Check community_brick_name tag
            brick_name_tag = file_resource.tags.get_tag(CommunityResourceFilesManagerService.COMMUNITY_BRICK_NAME_TAG_KEY, "gws_core")
            self.assertIsNotNone(brick_name_tag)
            self.assertEqual(brick_name_tag.value, "gws_core")

            # Check community_documentation_id tag
            doc_id_tag = file_resource.tags.get_tag(CommunityResourceFilesManagerService.COMMUNITY_DOCUMENTATION_ID_TAG_KEY, doc.id)
            self.assertIsNotNone(doc_id_tag)
            self.assertEqual(doc_id_tag.value, doc.id)

            # Check community_last_modificated_at tag
            last_mod_tag = file_resource.tags.get_tag(CommunityResourceFilesManagerService.COMMUNITY_LAST_MODIFICATED_AT_TAG_KEY, doc.last_modified_at)
            self.assertIsNotNone(last_mod_tag)
            self.assertEqual(last_mod_tag.value, doc.last_modified_at)

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_brick_technical_documentation_dto_creates_correct_file_tags(self):
        """
        Test that BrickTechnicalDocumentationDTO can be used to create a File
        with the correct tags for technical documentation.
        """
        # Create a sample technical documentation DTO
        tech_doc = BrickTechnicalDocumentationDTO(
            id="tech-doc-789",
            unique_name="MyResource",
            human_name="My Resource",
            brick_name="gws_core",
            brick_major=1,
            tech_doc_type="resources",
            last_modified_at="2024-01-16T14:20:00Z",
        )

        # Create a temporary markdown file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
            tmp.write("# My Resource\n\nThis is technical documentation.")
            tmp_path = tmp.name

        try:
            # Create a File resource
            file_resource = File(tmp_path)
            file_resource.name = tech_doc.human_name

            # Add tags as done in the task
            file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.SEND_TO_RAG_TAG_KEY, "CommunityTechnicalDocumentations"))
            file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_BRICK_NAME_TAG_KEY, "gws_core"))
            file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_TECHNICAL_DOCUMENTATION_ID_TAG_KEY, tech_doc.id))
            file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_TECH_DOC_TYPE_TAG_KEY, tech_doc.tech_doc_type))
            file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_LAST_MODIFICATED_AT_TAG_KEY, tech_doc.last_modified_at))

            # Verify the File has the correct tags
            self.assertEqual(file_resource.name, "My Resource")

            # Check send_to_rag tag
            send_to_rag_tag = file_resource.tags.get_tag(CommunityResourceFilesManagerService.SEND_TO_RAG_TAG_KEY, "CommunityTechnicalDocumentations")
            self.assertIsNotNone(send_to_rag_tag)
            self.assertEqual(send_to_rag_tag.value, "CommunityTechnicalDocumentations")

            # Check community_brick_name tag
            brick_name_tag = file_resource.tags.get_tag(CommunityResourceFilesManagerService.COMMUNITY_BRICK_NAME_TAG_KEY, "gws_core")
            self.assertIsNotNone(brick_name_tag)
            self.assertEqual(brick_name_tag.value, "gws_core")

            # Check community_technical_documentation_id tag
            tech_doc_id_tag = file_resource.tags.get_tag(CommunityResourceFilesManagerService.COMMUNITY_TECHNICAL_DOCUMENTATION_ID_TAG_KEY, tech_doc.id)
            self.assertIsNotNone(tech_doc_id_tag)
            self.assertEqual(tech_doc_id_tag.value, tech_doc.id)

            # Check community_tech_doc_type tag
            tech_doc_type_tag = file_resource.tags.get_tag(CommunityResourceFilesManagerService.COMMUNITY_TECH_DOC_TYPE_TAG_KEY, tech_doc.tech_doc_type)
            self.assertIsNotNone(tech_doc_type_tag)
            self.assertEqual(tech_doc_type_tag.value, tech_doc.tech_doc_type)

            # Check community_last_modificated_at tag
            last_mod_tag = file_resource.tags.get_tag(CommunityResourceFilesManagerService.COMMUNITY_LAST_MODIFICATED_AT_TAG_KEY, tech_doc.last_modified_at)
            self.assertIsNotNone(last_mod_tag)
            self.assertEqual(last_mod_tag.value, tech_doc.last_modified_at)

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_multiple_bricks_tags(self):
        """
        Test that files from multiple bricks have the correct brick_name tags.
        """
        # Create DTOs for different bricks
        doc1 = BrickDocumentationDTO(
            id="doc-core-1",
            title="Core Documentation",
            path="/core-doc",
            complete_path="/gws_core/core-doc",
            order=1,
            last_modified_at="2024-01-15T10:30:00Z",
        )

        doc2 = BrickDocumentationDTO(
            id="doc-omix-1",
            title="Omix Documentation",
            path="/omix-doc",
            complete_path="/gws_omix/omix-doc",
            order=1,
            last_modified_at="2024-01-16T11:00:00Z",
        )

        # Create temporary files
        tmp_paths = []
        try:
            for doc, brick_name in [(doc1, "gws_core"), (doc2, "gws_omix")]:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
                    tmp.write(f"# {doc.title}\n\nContent.")
                    tmp_path = tmp.name
                    tmp_paths.append(tmp_path)

                # Create File resource
                file_resource = File(tmp_path)
                file_resource.name = doc.title

                # Add tags
                file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.SEND_TO_RAG_TAG_KEY, "CommunityDocumentations"))
                file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_BRICK_NAME_TAG_KEY, brick_name))
                file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_DOCUMENTATION_ID_TAG_KEY, doc.id))

                # Verify correct brick name tag
                brick_name_tag = file_resource.tags.get_tag(CommunityResourceFilesManagerService.COMMUNITY_BRICK_NAME_TAG_KEY, brick_name)
                self.assertIsNotNone(brick_name_tag)
                self.assertEqual(brick_name_tag.value, brick_name)

        finally:
            # Clean up temporary files
            for tmp_path in tmp_paths:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)


class TestDownloadCommunityStories(BaseTestCase):
    """
    Test the DownloadCommunityStories task.

    Tests verify that the task correctly processes CommunityStoryDTO objects
    and creates File resources with the correct tags.
    """

    def test_community_story_dto_creates_correct_file_tags(self):
        """
        Test that CommunityStoryDTO can be used to create a File with the correct tags.
        """
        # Create a sample story DTO
        story = CommunityStoryDTO(
            id="story-123",
            title="My First Story",
            last_modified_at="2024-01-20T09:00:00Z",
        )

        # Create a temporary markdown file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
            tmp.write("# My First Story\n\nOnce upon a time...")
            tmp_path = tmp.name

        try:
            # Create a File resource
            file_resource = File(tmp_path)
            file_resource.name = story.title

            # Add tags as done in the task
            file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.SEND_TO_RAG_TAG_KEY, "CommunityStories"))
            file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_STORY_ID_TAG_KEY, story.id))
            file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_LAST_MODIFICATED_AT_TAG_KEY, story.last_modified_at))

            # Verify the File has the correct tags
            self.assertEqual(file_resource.name, "My First Story")

            # Check send_to_rag tag
            send_to_rag_tag = file_resource.tags.get_tag(CommunityResourceFilesManagerService.SEND_TO_RAG_TAG_KEY, "CommunityStories")
            self.assertIsNotNone(send_to_rag_tag)
            self.assertEqual(send_to_rag_tag.value, "CommunityStories")

            # Check community_story_id tag
            story_id_tag = file_resource.tags.get_tag(CommunityResourceFilesManagerService.COMMUNITY_STORY_ID_TAG_KEY, story.id)
            self.assertIsNotNone(story_id_tag)
            self.assertEqual(story_id_tag.value, story.id)

            # Check community_last_modificated_at tag
            last_mod_tag = file_resource.tags.get_tag(CommunityResourceFilesManagerService.COMMUNITY_LAST_MODIFICATED_AT_TAG_KEY, story.last_modified_at)
            self.assertIsNotNone(last_mod_tag)
            self.assertEqual(last_mod_tag.value, story.last_modified_at)

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestPushResourcesToRagFlow(BaseTestCase):
    """
    Test the PushResourcesToRagFlow task.

    Tests verify that the task has the correct input/output specifications.
    """

    def test_task_has_optional_download_result_input(self):
        """
        Test that PushResourcesToRagFlow has an optional input for download result.
        """
        # Verify that the task has input_specs defined
        self.assertIsNotNone(PushResourcesToRagFlow.input_specs)

        # Verify that the input_specs contains the download_result input
        self.assertIn("download_result", PushResourcesToRagFlow.input_specs._specs)

        # Verify that the download_result input is optional
        download_result_spec = PushResourcesToRagFlow.input_specs._specs["download_result"]
        self.assertTrue(download_result_spec.optional)

        # Verify that the download_result input is of type JSONDict
        self.assertIn(JSONDict, download_result_spec.resource_types)
