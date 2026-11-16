# MQTT_GetConnectPacketSize() rejects a CONNECT with a zero-length client identifier

MQTT 3.1.1 (section 3.1.3.1) allows a client to send a zero-length ClientId, provided CleanSession is set to 1. coreMQTT rejects it: MQTT_GetConnectPacketSize() returns MQTTBadParameter when clientIdentifierLength is 0, so a client cannot connect with a server-assigned identifier.

Expected:
- clientIdentifierLength == 0 with cleanSession == true is accepted (pClientIdentifier may be NULL or "").
- clientIdentifierLength == 0 with cleanSession == false is rejected with MQTTBadParameter (the spec requires CleanSession=1).
- A client identifier whose length and value disagree (NULL or "" with a non-zero length) is rejected with MQTTBadParameter.
