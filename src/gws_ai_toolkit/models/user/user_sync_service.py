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

    def get_user_type(self) -> type[User]:
        """
        Return the custom user model class type.

        :return: The AI Toolkit User model class
        :rtype: Type[User]
        """
        return User

    def from_gws_core_user(self, gws_core_user: GwsCoreUser) -> User:
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
        return User.from_gws_core_user(gws_core_user)
