"""Runtime protocol helpers built from a JSON schema.

Usage:
    from frogproto.msglib import load
    proto = load("protocol.json")
    msg = proto.msg.Testing.System.TEXTMSG(textdata="hi")
    encoded = msg.encode()
    enum_member, decoded = proto.decode_message(encoded)
"""

from __future__ import annotations

import enum
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import msgpack
from pydantic import BaseModel, create_model

MSGPACK_ENCODE_KW = {"use_bin_type": True}
MSGPACK_DECODE_KW = {"raw": False, "use_list": False}


class BinaryFlag(enum.IntFlag):
    NONE = 0
    ACK_REQUEST = 1
    ROUTE = 2


if hasattr(BaseModel, "model_config"):
    PayloadModelBase = type(
        "PayloadModelBase",
        (BaseModel,),
        {"model_config": {"extra": "forbid"}},
    )
else:
    PayloadModelBase = type(
        "PayloadModelBase",
        (BaseModel,),
        {"Config": type("Config", (), {"extra": "forbid"})},
    )


class MessageInstance:
    def __init__(self, proto: "Proto", enum_member: enum.IntEnum, payload_model: BaseModel):
        self.proto = proto
        self.enum_member = enum_member
        self.payload_model = payload_model

    def encode(self) -> bytes:
        return self.proto.encode_message(self)

    def dict(self) -> Dict[str, Any]:
        return {
            "msgid": self.proto.messageid(self.enum_member),
            "payload": _dump_model(self.payload_model),
        }


class _Namespace:
    def __init__(self, **entries: Any):
        self.__dict__.update(entries)


def _dump_model(model: BaseModel) -> Dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def _make_message_enum(
    name: str,
    members: Dict[str, int],
    payload_models: Dict[str, BaseModel],
    proto: "Proto",
) -> enum.IntEnum:
    enum_cls = enum.IntEnum(name, members)

    def payload(self, **kwargs: Any) -> BaseModel:
        model_cls = payload_models[self.name]
        return model_cls(**kwargs)

    def build(self, **kwargs: Any) -> MessageInstance:
        model = payload(self, **kwargs)
        return MessageInstance(proto, self, model)

    enum_cls.payload = payload
    enum_cls.__call__ = build
    enum_cls._payload_models = payload_models  # type: ignore[attr-defined]
    enum_cls._proto = proto  # type: ignore[attr-defined]
    return enum_cls


class Proto:
    def __init__(self, schema: Dict[str, Any]):
        self.schema = schema
        self.name: str = schema["PROTOCOL_NAME"]
        self.version: int = int(schema["PROTOCOL_VERSION"])

        self._id_to_enum: Dict[int, enum.IntEnum] = {}
        self._id_to_str: Dict[int, str] = {}
        self._payload_enums: Dict[str, enum.IntEnum] = {}

        self.enum = self._init_payload_enums(schema.get("enums", {}))
        self.msg, self.MessageCategory = self._init_messages(schema["messages"])

    def _init_payload_enums(self, enums_spec: Dict[str, Any]) -> _Namespace:
        enum_entries: Dict[str, enum.IntEnum] = {}
        for enum_name, members in enums_spec.items():
            member_values = {k: v for k, v in members.items() if k != "_info"}
            enum_cls = enum.IntEnum(enum_name, member_values)
            enum_entries[enum_name] = enum_cls
            self._payload_enums[enum_name] = enum_cls
        return _Namespace(**enum_entries)

    def _datatype_to_type(self, datatype: str, field_name: str):
        if datatype == "enum":
            return self._payload_enums[field_name]
        if datatype == "int":
            return int
        if datatype == "float":
            return float
        if datatype == "bool":
            return bool
        if datatype == "bytes":
            return bytes
        if datatype == "string":
            return str
        raise ValueError(f"Unsupported datatype '{datatype}' for field '{field_name}'")

    def _build_payload_model(self, path: str, fields: List[Dict[str, Any]]) -> BaseModel:
        model_fields: Dict[str, Tuple[Any, Any]] = {}
        for field in fields:
            f_name = field["name"]
            f_type = self._datatype_to_type(field["datatype"], f_name)
            model_fields[f_name] = (f_type, ...)

        model_name = path.replace(".", "_")
        return create_model(model_name, __base__=PayloadModelBase, __module__=__name__, **model_fields)  # type: ignore[return-value]

    def _init_messages(self, messages_spec: Dict[str, Any]) -> Tuple[_Namespace, enum.IntEnum]:
        categories: Dict[str, _Namespace] = {}
        category_values: Dict[str, int] = {}
        msg_id = 1

        for category_name, type_map in messages_spec.items():
            category_values[category_name] = len(category_values) + 1
            type_entries: Dict[str, enum.IntEnum] = {}

            for typ_name, message_map in type_map.items():
                member_values: Dict[str, int] = {}
                payload_models: Dict[str, BaseModel] = {}

                for msg_name, fields in message_map.items():
                    member_values[msg_name] = msg_id
                    path = f"{category_name}.{typ_name}.{msg_name}"
                    self._id_to_str[msg_id] = path
                    payload_models[msg_name] = self._build_payload_model(path, fields)
                    msg_id += 1

                enum_name = f"{category_name}_{typ_name}_Msg"
                enum_cls = _make_message_enum(enum_name, member_values, payload_models, self)
                type_entries[typ_name] = enum_cls
                for member in enum_cls:
                    self._id_to_enum[int(member.value)] = member

            categories[category_name] = _Namespace(**type_entries)

        message_category_enum = enum.IntEnum("MessageCategory", category_values)
        return _Namespace(**categories), message_category_enum

    def messageid(self, msg: Union[enum.IntEnum, MessageInstance]) -> int:
        enum_member = msg.enum_member if isinstance(msg, MessageInstance) else msg
        return int(enum_member.value)

    def message_str_from_id(self, msgid: int) -> str:
        return self._id_to_str[msgid]

    def get_message_enum(self, msgid: int) -> enum.IntEnum:
        return self._id_to_enum[msgid]

    def encode_message(self, msg: Union[enum.IntEnum, MessageInstance], payload_model: BaseModel | None = None) -> bytes:
        if isinstance(msg, MessageInstance):
            enum_member = msg.enum_member
            payload_model = msg.payload_model
        else:
            enum_member = msg
            payload_model = payload_model if payload_model is not None else enum_member.payload()

        payload_dict = _dump_model(payload_model)
        msgid = self.messageid(enum_member)
        return msgpack.packb((msgid, payload_dict), **MSGPACK_ENCODE_KW)

    def decode_message(self, encoded: bytes) -> Tuple[enum.IntEnum, Dict[str, Any]]:
        msgid, payload_raw = msgpack.unpackb(encoded, **MSGPACK_DECODE_KW)
        enum_member = self.get_message_enum(msgid)
        payload_model = enum_member.payload(**payload_raw)
        return enum_member, _dump_model(payload_model)


def load(source: Union[str, Path, Dict[str, Any]]) -> Proto:
    if isinstance(source, (str, Path)):
        data = json.loads(Path(source).read_text())
    elif isinstance(source, dict):
        data = source
    else:
        raise TypeError("source must be a path or a dict")
    return Proto(data)


__all__ = ["Proto", "load", "BinaryFlag", "MessageInstance"]
