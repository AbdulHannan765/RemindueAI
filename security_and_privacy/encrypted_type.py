from sqlalchemy.types import TypeDecorator, Text

from .user_private_info_encryption import (
    encrypt_value,
    decrypt_value,
)


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        return encrypt_value(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        return decrypt_value(value)