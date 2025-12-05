# frogproto

Runtime message packing helpers built from a JSON protocol spec (`frogproto/protocol/protocol.json` template). The first thing you do is point to a protocol file and load it.

```python
from frogproto import ProtoRuntime as Proto

# Use the template or your own JSON path
Proto.load(Proto.TEMPLATE_PROTOCOL_PATH)
Messages = Proto.Messages
PayloadEnum = Proto.PayloadEnum

msg = Messages.Testing.System.TEXTMSG(textdata="hi")
encoded = msg.encode()
enum_member, decoded = Proto.decode_message(encoded)
print(Proto.message_str_from_id(Proto.messageid(enum_member)), decoded)
```

See `example_msglib.py` for full canonical usage.
