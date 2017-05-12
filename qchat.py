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
import math
import hashlib
from datetime import datetime
from threading import Condition
import json

from dxlclient.callbacks import EventCallback
from dxlclient.client import DxlClient
from dxlclient.client_config import DxlClientConfig
from dxlclient.message import Event

from string import printable
from curses import erasechar, wrapper
from appJar import gui

# Import common logging and configuration
# Assume the common.py is in the CWD. Otherwise you'll need to add its location to the path
# sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
from common import *

# Configure local logger
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# Condition/lock used to protect changes to counter
event_count_condition = Condition()

# The events received (use an array so we can modify in callback)
event_count = [0]

# Create DXL configuration from file
config = DxlClientConfig.create_dxl_config_from_file(CONFIG_FILE)


# Set some globals
global username
global channel
global eventTopic
global UID
global joinTime
global currentUsers
global chatWin

# Login
def btnLogin(btn):
    global username
    global channel

    if btn=="Cancel":
        exit()
    else:
        username = str(loginApp.getEntry('user'))
        channel = str(loginApp.getEntry('channel'))
        # Here we can create and launch the subWindows
        loginApp.stop()

def btnSendMessage(btn):
    logger.info("Button Pressed")
    sendMessage()
    
def listUsers(currentUsers):
    results = []
    for user in currentUsers:
        results.append(currentUsers[user]['username'])

    return results

def rptTimeoutUsers():
    timeoutUsers()

def timeoutUsers():
    global currentUsers

    # Temp list of users who have NOT timed out
    refreshUsers={}
    for user in currentUsers:
        logger.info( "Time {0} and last ping {1}".format(str(int(time.time())), currentUsers[user]['lastping']))

        if int(time.time()) - int(currentUsers[user]['lastping']) < 300:
            refreshUsers[user]=currentUsers[user]
    
    currentUsers=refreshUsers
    usernames = listUsers(currentUsers)
    chatWin.updateListItems("listUsers",usernames)

def sendPingRequest():
    sendMessage(3)

def sendPing():
    sendMessage(2)

def sendMessage(msgType=1):
    # Record the start time
    start = int(time.time())
    # Create the event
    event = Event(eventTopic)

    if msgType == 1:
        # Set the payload
        event_dict={}
        #event type 1 is a standard chat message
        event_dict['type'] = 1
        event_dict['message'] = chatWin.getEntry("qcMessage")
        event_dict['time'] = str(int(time.time()))
        event_dict['user'] = username
        event_dict['UID'] = UID
    
    elif msgType ==2:
        logger.info("Sending Ping")
        # set the payload
        event_dict={}
        #event type 2 is a user notification message
        event_dict['type']=2
        event_dict['time'] = str(int(time.time()))
        event_dict['user'] = username
        event_dict['UID'] = UID

    elif msgType ==3:
        logger.info("Sending Ping Request")
        # set the payload
        event_dict={}
        #event type 3 is a broadcast ping request
        event_dict['type']=3

    elif msgType ==4:
        logger.info("Sending bye")
        # set the payload
        event_dict={}
        #event type 4 is a user GoodBye message
        event_dict['type']=4
        event_dict['time'] = str(int(time.time()))
        event_dict['user'] = username
        event_dict['UID'] = UID

   
    event.payload = json.dumps(event_dict).encode()
    
    
    # Send the event
    client.send_event(event)
    
    #cleanup the form
    chatWin.clearEntry("qcMessage")
    

def launch(win):
    loginApp.showSubWindow(win)

def menuPress(menuItem):
    if menuItem == "Exit":
        exit()

def checkStop():
    # Let everyone know you are leaving.
    sendMessage(4)
    
    return True



loginApp=gui("QChat for OpenDXL")

menus = ["-", "Exit"]
loginApp.addMenuList("File", menus, menuPress)

# Setup the login screen
loginApp.addLabel("title", "Welcome to QChat", 0, 0, 2)
loginApp.addLabel("user", "Username:", 1, 0)
loginApp.addEntry("user", 1, 1)
loginApp.addLabel("channel", "Channel:", 2, 0)
loginApp.addEntry("channel", 2, 1)
loginApp.addButtons(["Submit", "Cancel"], btnLogin, 3, 0, 2)
loginApp.setEntryFocus("user")
loginApp.enableEnter(btnLogin)

loginApp.go("winLogin")

UID = hashlib.md5(username+str(time.time())).hexdigest()

logger.info("UID: {0}".format(UID))

chatWin=gui("QChat for OpenDXL","940x596")
menus = ["-", "Exit"]
chatWin.addMenuList("File", menus, menuPress)

# Setup the chat screen
chatWin.setPadding([0,0])
chatWin.setInPadding([0,0])

# Setup DXL connectivity for chat
eventTopic = "/mcafee/event/qchat/{0}".format(channel)
logger.info( "Setting event topic")

with DxlClient(config) as client:
# Connect to the fabric
    logger.info( "Connecting to DXL fabric")
    client.connect()
    
    #
    # Register callback and subscribe
    #

    # Create and add event listener
    logger.info( "Setting up MyEventCallback class")
    class MyEventCallback(EventCallback):
        def on_event(self, event):
            with event_count_condition:
                global currentUsers
                message_dict=json.loads(event.payload.decode())
                # message types tell us how to process the event for chat
                # 1: standard message delivery
                # 2: current user stat (username, onchannel since, etc)
                # 3: Ping request
                # 4: BYE - A user has left the channel
                if message_dict['type'] ==1:
                    logger.info("Received message")
                    strTime = time.strftime("%H:%m:%S",time.localtime(int(message_dict['time'])))
                    strUsername = message_dict['user']
                    strMessage = "{0} {1}: {2}".format(strTime, strUsername, message_dict['message'])
                    strUID = message_dict['UID']
                        
                    # Print the payload for the received event
                    newConv = chatWin.getTextArea("txtConv")+"\n"+strMessage 
                    chatWin.enableTextArea("txtConv")
                    chatWin.clearTextArea("txtConv")
                    chatWin.setTextArea("txtConv",newConv)
                    chatWin.disableTextArea("txtConv")
                    chatWin.getTextAreaWidget("txtConv").see("end")
                    newConv = None
                    
                    # anytime we get information from the dxl, update the user list

                    # if the user does not yet exist, add her to the currentUsers
                    if currentUsers.get(strUID) == None:
                        currentUsers[strUID] = {}

                    currentUsers[strUID]['username']=strUsername
                    currentUsers[strUID]['onsince']=strTime
                    currentUsers[strUID]['lastping']=str(int(time.time()))

                    usernames = listUsers(currentUsers)
                    chatWin.updateListItems("listUsers",usernames)

                elif message_dict['type']==2:
                    # Do stuff with the user information
                    logger.info( "Received user information")
                    strTime = message_dict['time']
                    strUsername = message_dict['user']
                    strUID = message_dict['UID']
                    # if the user does not yet exist, add her to the currentUsers
                    if currentUsers.get(strUID) == None:
                        currentUsers[strUID] = {}

                    currentUsers[strUID]['username']=strUsername
                    currentUsers[strUID]['onsince']=strTime
                    currentUsers[strUID]['lastping']=str(int(time.time()))

                    usernames = listUsers(currentUsers)
                    chatWin.updateListItems("listUsers",usernames)

                elif message_dict['type']==3:
                    #Type 3 is a ping request. Everyone must reply with a ping
                    #This is compulsary
                    sendPing()

                elif message_dict['type']==4:
                    #Type 4 is a goodbye message. Someone told us he's leaving
                    #In order to purge him, set his last ping time to 0 and 
                    #rebuild the list
                    strUID = message_dict['UID']

                    if currentUsers.get(strUID) == None:
                        currentUsers[strUID] = {}

                    currentUsers[strUID]['lastping']=0
                    
                    rptTimeoutUsers()



                # Increment the count
                event_count[0] += 1
                # Notify that the count was increment
                event_count_condition.notify_all()

    # Register the callback with the client
    logger.info( "Adding event callback to the class instance")
    client.add_event_callback(eventTopic, MyEventCallback())
 
    #Start building the UI
    Conversation="{0}, welcome to QChat channel {1}.".format(username,channel)
    

    # Conversation window
    chatWin.addLabel("l1","Conversation: {0}@{1}".format(username,channel))
    chatWin.addScrolledTextArea("txtConv",1,0,8,4)
    chatWin.setTextAreaWidth("txtConv",80)
    chatWin.setTextAreaHeight("txtConv",25)
    chatWin.setTextArea("txtConv", Conversation)
    chatWin.disableTextArea("txtConv")
    chatWin.getTextAreaWidget("txtConv").see("end")
    
    
    currentUsers = {}
    currentUsers[UID] = {}
    currentUsers[UID]['username']=username
    currentUsers[UID]['onsince']=str(int(time.time()))
    currentUsers[UID]['lastping']=str(int(time.time()))

    usernames = listUsers(currentUsers)

    # Users window
    chatWin.addLabel("l2", "Users",0,8)
    chatWin.addListBox("listUsers",usernames,1,8,0,5)
    
    
    # Input Window
    chatWin.addEntry("qcMessage",6,0,8)
    chatWin.setEntryDefault("qcMessage", "QChat Message")
    chatWin.addButton("Send", btnSendMessage, 6, 8)
    chatWin.enableEnter(btnSendMessage)
    
    
    # Repeating events
    chatWin.registerEvent(rptTimeoutUsers)
    chatWin.setPollTime(60000)
    chatWin.registerEvent(sendPing)
    chatWin.setPollTime(60000)
    
    #Entry Calls
    sendPingRequest()
    chatWin.setEntryFocus("qcMessage")

    #Exit Calls
    chatWin.setStopFunction(checkStop)

    chatWin.go("chatWin")
