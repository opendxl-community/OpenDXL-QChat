#QChat (Quick Chat) is a simple chat room service leveraging
#the OpenDXL event invokation capabilities to create a small,
#light weight, and interactive chat room for use by incident
#responders and SOC personnel. This is an alpha released to
#be used to solicit ideation and to generate feedback. 
#Please send comments to jesse_netz@mcafee.com

import logging
import os
import sys
import time
from datetime import datetime
from threading import Condition
import json

from dxlclient.callbacks import EventCallback
from dxlclient.client import DxlClient
from dxlclient.client_config import DxlClientConfig
from dxlclient.message import Event

from string import printable
from curses import erasechar, wrapper

# Import common logging and configuration
# Assume the common.py is in the CWD. Otherwise you'll need to add its location to the path
# sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
from common import *

# Configure local logger
logging.getLogger().setLevel(logging.ERROR)
logger = logging.getLogger(__name__)



# Condition/lock used to protect changes to counter
event_count_condition = Condition()

# The events received (use an array so we can modify in callback)
event_count = [0]

# Create DXL configuration from file
config = DxlClientConfig.create_dxl_config_from_file(CONFIG_FILE)



PRINTABLE = map(ord, printable)
USERNAME = str(raw_input("Username? "))
CHANNEL = str(raw_input("Channel? "))
PROMPT = "{0}@{1} >>>".format(USERNAME,CHANNEL)

# The topic to publish to
EVENT_TOPIC = "/mcafee/event/qchat/{0}".format(CHANNEL)

def input(stdscr):
    ERASE = input.ERASE = getattr(input, "ERASE", ord(erasechar()))
    #Known backspace in Linux
    ERASE = 263

    Y, X = stdscr.getyx()
    s = []

    while True:
        c = stdscr.getch()

        if c in (13, 10):
            break
        elif c == ERASE:
            y, x = stdscr.getyx()
            if x > X:
                del s[-1]
                stdscr.move(y, (x - 1))
                stdscr.clrtoeol()
                stdscr.refresh()
        elif c in PRINTABLE:
            s.append(chr(c))
            stdscr.addch(c)

    return "".join(s)

def prompt(stdscr, y, x, prompt=">>> "):
    stdscr.move(y, x)
    stdscr.clrtoeol()
    stdscr.addstr(y, x, prompt)
    return input(stdscr)

def main(stdscr):
    Y, X = stdscr.getmaxyx()

    lines = []
    max_lines = (Y - 3)

    stdscr.clear()
    with DxlClient(config) as client:

        # Connect to the fabric
        client.connect()
    
        #
        # Register callback and subscribe
        #

        # Create and add event listener
        class MyEventCallback(EventCallback):
            def on_event(self, event):
                with event_count_condition:
                    message_dict=json.loads(event.payload.decode())
                    if message_dict['type'] ==1:
                        strTime = time.strftime("%H:%m:%S",time.localtime(int(message_dict['time'])))
                        strUsername = message_dict['user']
                        strMessage = "{0} {1}: {2}".format(strTime, strUsername, message_dict['message'])
                        
                    # Print the payload for the received event
                    stdscr.addstr(len(lines), 0, strMessage)
                    lines.append(strMessage)
                    stdscr.move(Y-1, len(PROMPT))
                
                    stdscr.refresh()
                    # Increment the count
                    event_count[0] += 1
                    # Notify that the count was increment
                    event_count_condition.notify_all()

        # Register the callback with the client
        client.add_event_callback(EVENT_TOPIC, MyEventCallback())

        # Record the start time
        start = time.time()

        # Create the event
        event = Event(EVENT_TOPIC)
        # Set the payload
        
        while True:
            currentMessage = prompt(stdscr, (Y - 1), 0, PROMPT)  # noqa
            #print "HERE"
            if currentMessage == "\q":
                break
    
            # scroll
            if len(lines) > max_lines:
                lines = lines[1:]
                stdscr.clear()
                for i, line in enumerate(lines):
                    stdscr.addstr(i, 0, line)

            event_dict={}
            #event type 1 is a standard chat message
            event_dict['type'] = 1
            event_dict['message'] = currentMessage
            event_dict['time'] = time.time()
            event_dict['user'] = USERNAME

            event.payload = json.dumps(event_dict).encode()


            # Send the event
            client.send_event(event)
    

#Execute main function
wrapper(main)

