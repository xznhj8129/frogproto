# frogproto

Runtime message packing helpers built from a JSON protocol spec (`frogproto/protocol.json` template). Point to a protocol file, load it, and use the returned object.

```python
from frogproto import load

proto = load("protocol.json")  # or your own path/dict
msg = proto.msg.Testing.System.TEXTMSG(textdata="hi")
encoded = msg.encode()
enum_member, decoded = proto.decode_message(encoded)
print(proto.message_str_from_id(proto.messageid(enum_member)), decoded)
```

See `example_msglib.py` for full canonical usage.
