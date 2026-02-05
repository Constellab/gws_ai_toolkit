from gws_core.core.model.model_dto import BaseModelDTO


class BrickDocumentationDTO(BaseModelDTO):
    """DTO for a brick documentation item from Community."""
    id: str
    title: str
    path: str
    complete_path: str
    order: int
    last_modified_at: str | None = None

    @classmethod
    def from_community_json_response(cls, data: dict):
        """Populate the DTO from Community API JSON data."""
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            path=data.get("path", ""),
            complete_path=data.get("completePath", ""),
            order=data.get("order", 0),
            last_modified_at=data.get("lastModifiedAt"),
        )


class BrickTechnicalDocumentationDTO(BaseModelDTO):
    """DTO for a brick technical documentation item from Community."""
    id: str
    last_modified_at: str | None = None
    brick_name: str
    brick_major: int
    unique_name: str
    human_name: str
    tech_doc_type: str | None = None  # Will be set when parsing the response dict

    @classmethod
    def from_community_json_response(cls, data: dict, tech_doc_type: str | None = None):
        """Populate the DTO from Community API JSON data."""
        return cls(
            id=data.get("id", ""),
            last_modified_at=data.get("lastModifiedAt"),
            brick_name=data.get("brickName", ""),
            brick_major=data.get("brickMajor", 0),
            unique_name=data.get("uniqueName", ""),
            human_name=data.get("humanName", ""),
            tech_doc_type=tech_doc_type,
        )


class CommunityStoryDTO(BaseModelDTO):
    """DTO for a Community story item."""
    id: str
    title: str
    last_modified_at: str | None = None

    @classmethod
    def from_community_json_response(cls, data: dict):
        """Populate the DTO from Community API JSON data."""
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            last_modified_at=data.get("lastModifiedAt"),
        )
