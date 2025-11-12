
from gws_core import (GenerateShareLinkDTO, ShareLinkEntityType,
                      ShareLinkService)


class Utils:

    @classmethod
    def generate_temp_share_resource_link(cls, resource_id: str) -> str | None:
        """Generate a temporary share link for a resource.

        Usefull to view a resource from reflex app
        """
        # Generate a public share link for the document
        generate_link_dto = GenerateShareLinkDTO.get_1_hour_validity(
            entity_id=resource_id,
            entity_type=ShareLinkEntityType.RESOURCE
        )

        share_link = ShareLinkService.get_or_create_valid_public_share_link(generate_link_dto)

        if share_link:
            return share_link.get_public_link()
        return None
