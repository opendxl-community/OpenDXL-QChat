# OpenDXL-QChat
QChat (Quick Chat) is a chat room service leveraging the OpenDXL event invokation capabilities to create small, light-weight, and interactive chat rooms for use by incident responders and SOC personnel.

## Introduction

QChat leverages event invokation to broadcast realtime messages across the channel utilizing DXL's message topics. Authentication can be controlled through topic authorization, or left open for discretionary access to the channel. Topics are dynamically generated when the first participant enters the channel. Each subsequent participant will sit on that topic. Some benefits include but are not limited to: ephemeral, moderator free, encrypted, high speed and always connected, infrastructure free, and already integrated into existing connected platform for quick actions during high-stress incident response activities.

![Login](http://i.imgur.com/nThJP92.png "Login Screen")

![Chat](http://i.imgur.com/DOBO3Nm.png "Chat Window")


## Startup
  During startup, the participant is asked for username and channel id. As a proof-of-concept this can be altered in later versions to be entered in a config or stored locally in a cache after initial log in. 
 
## Chat screen

  Once DXL fabric connection is established, the participant listens for any incoming events on the channel. These events are json form and parsed appropriately. Currently, message type = 1 is supported, but built to handle future types as well (events, methods, property sets, and more). 
  
  The screen is drawn using the python `curses` library. As such, multi-line submissions are not permitted in the PoC. This can be addressed in extended submissions of the code.
   
  

### Future capabilities in progress include:
  * 1 on 1 user chat
  * Integrate with other DXL capabilities (TIE and MAR)
  * Send chat content to ServiceNow ticket*
  


## Setup

### McAfee OpenDXL SDK

https://www.mcafee.com/us/developers/open-dxl/index.aspx

McAfee Threat Intelligence Exchange (TIE) DXL Python Client Library at the follow link:

https://github.com/opendxl/opendxl-tie-client-python/wiki

* Certificate Files Creation [link](https://opendxl.github.io/opendxl-client-python/pydoc/certcreation.html)
* ePO Certificate Authority (CA) Import [link](https://opendxl.github.io/opendxl-client-python/pydoc/epocaimport.html)
* ePO Broker Certificates Export  [link](https://opendxl.github.io/opendxl-client-python/pydoc/epobrokercertsexport.html)



#### Edit the dxlclient.config
```
[Certs]
BrokerCertChain=certs/brokercert.crt
CertFile=certs/client.crt
PrivateKey=certs/client.key

[Brokers]
{}={};8883;
```
