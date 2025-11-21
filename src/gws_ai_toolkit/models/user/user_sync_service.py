

from typing import Type

from gws_core import User as GwsCoreUser
from gws_core import UserSyncService, event_listener

from .user import User


@event_listener
class AiToolkitUserSyncService(UserSyncService[User]):
    """
    Service for synchronizing users from gws_core database to gws_ai_toolkit database.

    This service automatically syncs users when user events occur:
    - system.started: Syncs all users from gws_core when the system starts
    - user.created: Syncs the newly created user
    - user.updated: Syncs the updated user
    - user.activated: Syncs the user when activated/deactivated

    The service is decorated with @event_listener to register it with the event system.
    """

    def get_user_type(self) -> Type[User]:
        """
        Return the custom user model class type.

        :return: The AI Toolkit User model class
        :rtype: Type[User]
        """
        return User

    def update_custom_user_attributes(self, custom_user: User, gws_core_user: GwsCoreUser) -> User:
        """
        Update the attributes of an AI Toolkit user object with data from a gws_core user.

        This method copies all relevant fields from the gws_core user to the
        AI Toolkit user object and returns the updated object.

        IMPORTANT: This method only updates the object attributes.
        It does NOT save it to the database.

        :param custom_user: The AI Toolkit user object to update
        :type custom_user: User
        :param gws_core_user: The source User object from gws_core
        :type gws_core_user: GwsCoreUser
        :return: The updated AI Toolkit user object (NOT saved to database)
        :rtype: User
        """
        custom_user.email = gws_core_user.email
        custom_user.first_name = gws_core_user.first_name
        custom_user.last_name = gws_core_user.last_name
        custom_user.group = gws_core_user.group
        custom_user.is_active = gws_core_user.is_active
        custom_user.photo = gws_core_user.photo
        return custom_user
