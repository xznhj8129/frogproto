# frogproto

Runtime message packing helpers built from a JSON protocol spec (`frogproto/protocol/protocol.json`). The protocol is loaded at import time; override it with `load_protocol(<path or dict>)` if you want a different schema.

```python
from frogproto import Messages, PayloadEnum, encode_message, decode_message, messageid, message_str_from_id

# Optional: load_protocol("custom_protocol.json")

msg = Messages.Testing.System.TEXTMSG(textdata="hi")
encoded = msg.encode()
enum_member, decoded = decode_message(encoded)
print(message_str_from_id(messageid(enum_member)), decoded)
```

See `example_msglib.py` for full canonical usage.
