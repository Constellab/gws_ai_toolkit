

from typing import List

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_core import EnumField, Model, UserDTO, UserGroup
from peewee import BooleanField, CharField


class User(Model):

    email: str = CharField(default=False, index=True)
    first_name: str = CharField(default=False)
    last_name: str = CharField(default=False)
    group: UserGroup = EnumField(choices=UserGroup,
                                 default=UserGroup.USER)
    is_active = BooleanField(default=True)

    photo: str = CharField(null=True)

    def to_dto(self) -> UserDTO:
        return UserDTO(
            id=self.id,
            email=self.email,
            first_name=self.first_name,
            last_name=self.last_name,
            photo=self.photo
        )

    @classmethod
    def get_real_users(cls) -> List['User']:
        """Get all real users (excluding SYSUSER) that are active.

        :return: Query of real users ordered by first and last name
        :rtype: ModelSelect
        """
        return list(User.select().where(
            (User.group != UserGroup.SYSUSER)
        ).order_by(User.first_name, User.last_name))

    class Meta:
        table_name = 'gws_ai_toolkit_user'
        database = AiToolkitDbManager.get_instance().db
        is_table = True
        db_manager = AiToolkitDbManager.get_instance()
