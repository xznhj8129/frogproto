from pathlib import Path
import frogproto.msglib as fp

Proto = fp.ProtoRuntime
Proto.load("protocol.json")
Messages = Proto.Messages
PayloadEnum = Proto.PayloadEnum


print("=== FLIGHT message ===")
lat = 15.833455
lon = 20.898841
msg_instance = Messages.Status.System.FLIGHT(
    airspeed=100,
    FlightMode=PayloadEnum.FlightMode.LOITER,
    groundspeed=100,
    heading=0,
    msl_alt=100,
    lat=int(lat * 1e7),
    lon=int(lon * 1e7),
)
obj = msg_instance.dict()
print("Object:", obj)

encoded_msg = msg_instance.encode()
print("Message str:", Proto.message_str_from_id(Proto.messageid(msg_instance.enum_member)))
print("Payload:", obj["payload"])
print("Encoded length:", len(encoded_msg))

enum_member, decoded_payload = Proto.decode_message(encoded_msg)
print("Decoded enum:", enum_member)
print("Decoded payload:", decoded_payload)
print("Decoded msg str:", Proto.message_str_from_id(Proto.messageid(enum_member)))
print()

print("=== TEXT message ===")
msg_enum = Messages.Testing.System.TEXTMSG
try:
    msg_enum(textdata=b"testing")
except Exception as e:
    print("Expected failure on wrong type:", e)

msg_instance = msg_enum(textdata="testing")
encoded_msg = msg_instance.encode()
print("Message str:", Proto.message_str_from_id(Proto.messageid(msg_enum)))
print("Payload:", msg_instance.dict()["payload"])
print("Encoded length:", len(encoded_msg))

enum_member, decoded_payload = Proto.decode_message(encoded_msg)
print("Decoded enum:", enum_member)
print("Decoded payload:", decoded_payload)
print("Decoded msg str:", Proto.message_str_from_id(Proto.messageid(enum_member)))
