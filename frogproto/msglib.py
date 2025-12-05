import json
from pathlib import Path
from typing import Dict, Optional, Any
from enum import Enum, IntEnum, IntFlag
import msgpack

type_mapping = {
    "int": int,
    "float": float,
    "string": str,
    "bool": bool,
    "enum": IntEnum,
    "bytes": bytes,
}


class BinaryFlag(IntFlag):
    EXAMPLE_1 = 1 << 0
    EXAMPLE_2 = 1 << 1
    EXAMPLE_3 = 1 << 2
    EXAMPLE_4 = 1 << 3
    EXAMPLE_5 = 1 << 4
    EXAMPLE_6 = 1 << 5
    EXAMPLE_7 = 1 << 6
    EXAMPLE_8 = 1 << 7


class ProtoRuntime:
    MessageCategory: Optional[IntEnum] = None
    Messages: Optional[type] = None
    PayloadEnum: Optional[type] = None
    PROTOCOL_NAME: Optional[str] = None
    PROTOCOL_VERSION: Optional[int] = None

    @classmethod
    def _load_spec(cls, source: Any) -> Dict[str, Any]:
        if source is None:
            raise RuntimeError("Protocol path or object must be provided")
        if isinstance(source, (str, Path)):
            path = Path(source)
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        if isinstance(source, dict):
            return source
        raise TypeError("Protocol source must be path-like or dict")

    @staticmethod
    def _build_payload_enum(enum_spec: Dict[str, Dict[str, Any]]) -> type:
        payload_enum_cls = type("PayloadEnum", (), {})
        for enum_name, members in enum_spec.items():
            member_dict = {k: v for k, v in members.items() if not k.startswith("_")}
            if not member_dict:
                raise ValueError(f"Enum {enum_name} has no members")
            setattr(payload_enum_cls, enum_name, IntEnum(enum_name, member_dict))
        return payload_enum_cls

    @classmethod
    def _build_messages(cls, messages_spec: Dict[str, Any]) -> Any:
        messages_cls = type("Messages", (), {})
        category_members: Dict[str, int] = {}

        for cat_idx, (cat_name, subcats) in enumerate(messages_spec.items(), start=1):
            if not isinstance(subcats, dict):
                raise ValueError(f"Protocol Error: Category {cat_name} must map to subcategories")
            category_members[cat_name] = cat_idx
            category_cls = type(cat_name, (), {})

            for sub_idx, (sub_name, msg_defs) in enumerate(subcats.items(), start=1):
                if not isinstance(msg_defs, dict) or not msg_defs:
                    raise ValueError(f"Protocol Error: Subcategory {cat_name}.{sub_name} must map to messages")
                msg_members = {msg_name: i for i, msg_name in enumerate(msg_defs.keys(), start=1)}
                sub_enum = IntEnum(sub_name, msg_members)
                sub_enum.value_subcat = sub_idx
                sub_enum.str = sub_name
                sub_enum.category = category_cls
                sub_enum.category_name = cat_name
                sub_enum.category_value = cat_idx
                sub_enum.subcategory_name = sub_name
                sub_enum.subcategory_value = sub_idx

                for msg_name, payload_def in msg_defs.items():
                    if not isinstance(payload_def, list):
                        raise ValueError(f"Protocol Error: Payload for {cat_name}.{sub_name}.{msg_name} must be a list")
                    sub_enum[msg_name].payload_def = payload_def

                setattr(category_cls, sub_name, sub_enum)

            category_cls.value_cat = cat_idx
            category_cls.str = cat_name
            setattr(messages_cls, cat_name, category_cls)

        return IntEnum("MessageCategory", category_members), messages_cls

    @classmethod
    def load(cls, source: Any) -> Dict[str, Any]:
        spec = cls._load_spec(source)
        messages_spec = spec.get("messages")
        enum_spec = spec.get("enums", {})
        if not isinstance(messages_spec, dict) or not messages_spec:
            raise ValueError("Protocol Error: 'messages' missing or invalid in protocol JSON")
        if not isinstance(enum_spec, dict):
            raise ValueError("Protocol Error: 'enums' must be a mapping")
        cls.PayloadEnum = cls._build_payload_enum(enum_spec)
        cls.MessageCategory, cls.Messages = cls._build_messages(messages_spec)
        cls.PROTOCOL_NAME = spec.get("PROTOCOL_NAME")
        cls.PROTOCOL_VERSION = spec.get("PROTOCOL_VERSION")
        cls._attach_payload_helpers()

        g = globals()
        g["MessageCategory"] = cls.MessageCategory
        g["Messages"] = cls.Messages
        g["PayloadEnum"] = cls.PayloadEnum
        g["PROTOCOL_NAME"] = cls.PROTOCOL_NAME
        g["PROTOCOL_VERSION"] = cls.PROTOCOL_VERSION
        return spec

    @classmethod
    def _require_loaded(cls):
        if cls.MessageCategory is None or cls.Messages is None or cls.PayloadEnum is None:
            raise RuntimeError("Protocol is not loaded")

    @classmethod
    def messageid(cls, msg):
        cls._require_loaded()
        try:
            category_value = msg.__class__.category_value
            subcategory_value = msg.__class__.value_subcat
        except AttributeError as e:
            raise ValueError(f"Invalid message enum: {msg}") from e
        message_value = msg.value
        return (category_value, subcategory_value, message_value)

    @classmethod
    def message_str_from_id(cls, msg_id):
        cls._require_loaded()
        category_value, subcategory_value, message_value = msg_id
        try:
            category_enum = cls.MessageCategory(category_value)
            category_name = category_enum.name
        except ValueError as e:
            raise ValueError(f"Protocol Error: Invalid category value: {category_value}") from e

        category_class = getattr(cls.Messages, category_name)
        subcategory_name = None
        for attr in dir(category_class):
            if attr.startswith('_'):
                continue
            subcategory_class = getattr(category_class, attr)
            if hasattr(subcategory_class, 'value_subcat') and isinstance(subcategory_class.value_subcat, int):
                if subcategory_class.value_subcat == subcategory_value:
                    subcategory_name = attr
                    break
        if subcategory_name is None:
            raise ValueError(f"Protocol Error: No subcategory found with value {subcategory_value} in category {category_name}")

        message_enum = getattr(category_class, subcategory_name)
        message_name = None
        for member in message_enum:
            if member.value == message_value:
                message_name = member.name
                break
        if message_name is None:
            raise ValueError(f"Protocol Error: No message found with value {message_value} in {category_name}.{subcategory_name}")

        return f"{category_name}.{subcategory_name}.{message_name}"

    @classmethod
    def get_message_enum(cls, category_value, subcategory_value, message_value):
        cls._require_loaded()
        try:
            category_enum = cls.MessageCategory(category_value)
            category_name = category_enum.name
        except ValueError as e:
            raise ValueError(f"Protocol Error: Invalid category value: {category_value}") from e

        category_class = getattr(cls.Messages, category_name)
        for attr in dir(category_class):
            if attr.startswith('_'):
                continue
            subcategory_class = getattr(category_class, attr)
            if hasattr(subcategory_class, 'value_subcat') and subcategory_class.value_subcat == subcategory_value:
                break
        else:
            raise ValueError(f"Protocol Error: No subcategory found with value {subcategory_value} in category {category_name}")

        try:
            enum_member = subcategory_class(message_value)
        except ValueError as e:
            raise ValueError(f"Protocol Error: No message found with value {message_value} in {category_name}.{subcategory_class.__name__}") from e

        return enum_member

    @classmethod
    def create_payload(cls, enum_member, **kwargs):
        cls._require_loaded()
        if not hasattr(enum_member, 'payload_def'):
            raise ValueError(f"Protocol Error: No payload definition for {enum_member}")

        field_defs = {}
        for field in enum_member.payload_def:
            field_name = field["name"]
            key_name = field_name[len("PayloadEnum_"):] if field_name.startswith("PayloadEnum_") else field_name
            field_defs[key_name] = {"type": field.get("datatype"), "is_enum": field.get("datatype") == "enum"}

        required_keys = set(field_defs.keys())
        provided_keys = set(kwargs.keys())
        if required_keys != provided_keys:
            missing = required_keys - provided_keys
            extra = provided_keys - required_keys
            if missing:
                raise ValueError(f"Protocol Error: Missing required fields: {missing}")
            if extra:
                raise ValueError(f"Protocol Error: Extra fields provided: {extra}")

        plist = []
        for field in enum_member.payload_def:
            field_name = field["name"]
            key = field_name[len("PayloadEnum_"):] if field_name.startswith("PayloadEnum_") else field_name
            value = kwargs[key]
            field_info = field_defs[key]

            if field_info["is_enum"]:
                enum_cls = getattr(cls.PayloadEnum, key, None)
                if enum_cls is None:
                    raise ValueError(f"Protocol Error: Enum class {key} not found in PayloadEnum")
                if not isinstance(value, enum_cls):
                    raise TypeError(f"Protocol Error: Field '{key}' expects an instance of {key}, got {type(value).__name__}")
            else:
                expected_type = type_mapping.get(field_info["type"])
                if expected_type is None:
                    raise ValueError(f"Protocol Error: Unknown datatype '{field_info['type']}' for field '{key}'")
                if not isinstance(value, expected_type):
                    raise TypeError(f"Protocol Error: Field '{key}' expects {expected_type.__name__}, got {type(value).__name__}")

            plist.append(value)

        return plist

    @classmethod
    def encode_message(cls, msg_enum, payload=[]):
        cls._require_loaded()
        category, subcategory, msgtype = cls.messageid(msg_enum)
        return msgpack.packb([category, subcategory, msgtype, payload])

    @classmethod
    def decode_message(cls, data):
        cls._require_loaded()
        category, subcategory, msgtype, payload_list = msgpack.unpackb(data, use_list=True)
        enum_member = cls.get_message_enum(category, subcategory, msgtype)
        if not hasattr(enum_member, 'payload_def'):
            raise ValueError(f"Protocol Error: No payload definition for {enum_member}")

        payload_def = enum_member.payload_def
        if len(payload_def) != len(payload_list):
            raise ValueError(f"Protocol Error: Payload list length {len(payload_list)} does not match definition {len(payload_def)}")

        payload_dict = {}
        for field, value in zip(payload_def, payload_list):
            field_name = field["name"]
            key = field_name[len("PayloadEnum_"):] if field_name.startswith("PayloadEnum_") else field_name
            datatype = field.get("datatype")
            if datatype == "enum":
                enum_cls = getattr(cls.PayloadEnum, key, None)
                if enum_cls is None:
                    raise ValueError(f"Protocol Error: Enum class {key} not found in PayloadEnum")
                value = enum_cls(value)
            elif datatype == "string" and isinstance(value, (bytes, bytearray)):
                value = value.decode('utf-8')

            payload_dict[key] = value

        return enum_member, payload_dict

    @classmethod
    def _attach_payload_helpers(cls):
        if cls.Messages is None:
            return
        for category_name in dir(cls.Messages):
            if category_name.startswith('_'):
                continue
            category = getattr(cls.Messages, category_name)
            for subcategory_name in dir(category):
                if subcategory_name.startswith('_'):
                    continue
                subcategory = getattr(category, subcategory_name)
                if isinstance(subcategory, type) and issubclass(subcategory, Enum):
                    setattr(subcategory, 'payload', lambda self, **kwargs: cls.create_payload(self, **kwargs))

                    def _instance_builder(self, **kwargs):
                        plist = cls.create_payload(self, **kwargs)
                        ordered = {}
                        for field in self.payload_def:
                            fname = field["name"]
                            key = fname[len("PayloadEnum_"):] if fname.startswith("PayloadEnum_") else fname
                            ordered[key] = kwargs[key]
                        return MessageInstance(self, plist, ordered)

                    setattr(subcategory, '__call__', _instance_builder)


class MessageInstance:
    __slots__ = ("enum_member", "payload_list", "payload_dict")

    def __init__(self, enum_member, payload_list, payload_dict):
        self.enum_member = enum_member
        self.payload_list = payload_list
        self.payload_dict = payload_dict

    def encode(self) -> bytes:
        return ProtoRuntime.encode_message(self.enum_member, self.payload_list)

    def as_object(self) -> Dict[str, Any]:
        return {
            "msgid": ProtoRuntime.message_str_from_id(ProtoRuntime.messageid(self.enum_member)),
            "payload": self.payload_dict
        }

    def dict(self) -> Dict[str, Any]:
        return self.as_object()


def load_protocol(source: Any):
    return ProtoRuntime.load(source)


def messageid(msg):
    return ProtoRuntime.messageid(msg)


def message_str_from_id(msg_id):
    return ProtoRuntime.message_str_from_id(msg_id)


def get_message_enum(category_value, subcategory_value, message_value):
    return ProtoRuntime.get_message_enum(category_value, subcategory_value, message_value)


def create_payload(enum_member, **kwargs):
    return ProtoRuntime.create_payload(enum_member, **kwargs)


def encode_message(msg_enum, payload=[]):
    return ProtoRuntime.encode_message(msg_enum, payload)


def decode_message(data):
    return ProtoRuntime.decode_message(data)


MessageCategory = None
Messages = None
PayloadEnum = None
PROTOCOL_NAME = None
PROTOCOL_VERSION = None

__all__ = [
    "ProtoRuntime",
    "MessageCategory",
    "Messages",
    "PayloadEnum",
    "BinaryFlag",
    "PROTOCOL_NAME",
    "PROTOCOL_VERSION",
    "messageid",
    "message_str_from_id",
    "get_message_enum",
    "create_payload",
    "MessageInstance",
    "encode_message",
    "decode_message",
    "load_protocol",
]
