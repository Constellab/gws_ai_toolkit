"""Where the knowledge-base stack gets its API key from.

A lab that never exported ``OPENAI_API_KEY`` must still be able to index and chat, so a named
credentials entry wins over the lab-wide setting. The failure cases matter as much as the happy one:
each has to name what is wrong, because the alternative is an authentication error from the provider
several layers away from the configuration that caused it.
"""

import os

from gws_ai_toolkit.rag.knowledge_base.knowledge_base_credentials import (
    API_KEY_ENTRY_NAMES,
    resolve_openai_api_key,
)
from gws_core import BaseTestCase, CredentialsDataOther, CredentialsDataS3, CredentialsService
from gws_core.credentials.credentials_type import SaveCredentialsDTO


# test_knowledge_base_credentials
class TestKnowledgeBaseCredentials(BaseTestCase):
    """The credentials helper: named entry first, lab setting as the fallback."""

    @staticmethod
    def _create_other_credentials(name: str, data: dict) -> None:
        """Create an 'other' credentials entry holding the given key / value pairs."""
        CredentialsService.create(
            SaveCredentialsDTO(
                name=name,
                type=CredentialsDataOther.get_type_id(),
                description="Knowledge base test credentials",
                data={"data": [{"key": key, "value": value} for key, value in data.items()]},
            )
        )

    def test_a_named_entry_provides_the_key(self):
        """The configured credentials are what a lab uses instead of a process-wide variable."""
        self._create_other_credentials("kb_openai", {"api_key": "sk-from-credentials"})

        self.assertEqual(resolve_openai_api_key("kb_openai"), "sk-from-credentials")

    def test_every_accepted_entry_name_is_read(self):
        """The key may be named any of the accepted entries, so an existing entry keeps working."""
        for index, entry_name in enumerate(API_KEY_ENTRY_NAMES):
            credentials_name = f"kb_openai_{index}"
            self._create_other_credentials(credentials_name, {entry_name: f"sk-{entry_name}"})

            self.assertEqual(resolve_openai_api_key(credentials_name), f"sk-{entry_name}")

    def test_the_lab_setting_is_the_fallback(self):
        """With no credentials named, the key comes from the lab — what the brick already relies on."""
        previous_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "sk-from-lab-settings"
        try:
            self.assertEqual(resolve_openai_api_key(), "sk-from-lab-settings")
            self.assertEqual(resolve_openai_api_key(None), "sk-from-lab-settings")
        finally:
            if previous_key is None:
                del os.environ["OPENAI_API_KEY"]
            else:
                os.environ["OPENAI_API_KEY"] = previous_key

    def test_unknown_credentials_are_named_in_the_error(self):
        """A typo in a configuration screen has to say which name did not resolve."""
        with self.assertRaises(ValueError) as raised:
            resolve_openai_api_key("does_not_exist")

        self.assertIn("does_not_exist", str(raised.exception))

    def test_credentials_of_the_wrong_type_are_rejected(self):
        """An S3 entry holds no API key, and saying so beats reading a missing field as None."""
        CredentialsService.create(
            SaveCredentialsDTO(
                name="kb_s3",
                type=CredentialsDataS3.get_type_id(),
                description="Not an API key",
                data={
                    "endpoint_url": "http://localhost:9000",
                    "region": "eu-west-1",
                    "access_key_id": "access",
                    "secret_access_key": "secret",
                },
            )
        )

        with self.assertRaises(ValueError) as raised:
            resolve_openai_api_key("kb_s3")

        self.assertIn("other", str(raised.exception))

    def test_credentials_without_a_recognised_entry_list_what_was_expected(self):
        """The message names the accepted entries, so the fix is in the message."""
        self._create_other_credentials("kb_openai_empty", {"token": "sk-wrong-entry-name"})

        with self.assertRaises(ValueError) as raised:
            resolve_openai_api_key("kb_openai_empty")

        for entry_name in API_KEY_ENTRY_NAMES:
            self.assertIn(entry_name, str(raised.exception))
