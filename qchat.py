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
import re

from dxlclient.callbacks import EventCallback
from dxlclient.client import DxlClient
from dxlclient.client_config import DxlClientConfig
from dxlclient.message import Event

from dxltieclient import TieClient
from dxltieclient.constants import HashType, ReputationProp, FileProvider, FileEnterpriseAttrib, CertProvider, CertEnterpriseAttrib, AtdAttrib, TrustLevel, EpochMixin

from dxlmarclient import MarClient, ResultConstants, ProjectionConstants, ConditionConstants, SortConstants, OperatorConstants

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

hashType = None

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
    #chatWin.updateListItems("listUsers",usernames)
    # Updated to refer to new appJar method
    chatWin.updateListBox("listUsers",usernames)

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

        #cleanup the form
        chatWin.clearEntry("qcMessage")
    
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
    
    

def launch(win):
    loginApp.showSubWindow(win)

def menuPress(menuItem):
    if menuItem == "Exit":
        exit()

    elif menuItem == "Hash Investigation":
        chatWin.showSubWindow("Hash Investigation")
        #Do stuff here to show Hash investigation window

def validateHash(ve):
    #Validates if the submitted value is an MD5, SHA1, or SHA256 hash value
    global hashType

    strHash=chatWin.getEntry(ve)
    logger.info( "Check value {0} against hash review.".format(str(strHash)))
    md5Test=re.match('[A-Fa-f0-9]{32}$',strHash)
    logger.info( "MD5 result: {0}".format(str(md5Test)))
    sha1Test=re.match('[A-Fa-f0-9]{40}$',strHash)
    logger.info( "MD5 result: {0}".format(str(sha1Test)))
    sha256Test=re.match('[A-Fa-f0-9]{64}$',strHash)
    logger.info( "MD5 result: {0}".format(str(sha256Test)))

    if md5Test:
        hashType="md5"
        chatWin.setEntryValid("TIE_Hash")
        chatWin.enableButton("Get Reputations")
        chatWin.enableButton("ActiveResponse Get Systems")
    elif sha1Test:
        hashType="sha1"
        chatWin.setEntryValid("TIE_Hash")
        chatWin.enableButton("Get Reputations")
        chatWin.enableButton("ActiveResponse Get Systems")
    elif sha256Test:
        hashType="sha256"
        chatWin.setEntryValid("TIE_Hash")
        chatWin.enableButton("Get Reputations")
        chatWin.disableButton("ActiveResponse Get Systems")
    else:
        chatWin.setEntryInvalid("TIE_Hash")
        chatWin.disableButton("Get Reputations")
        chatWin.disableButton("ActiveResponse Get Systems")

    return True

def checkStop():
    # Let everyone know you are leaving.
    sendMessage(4)
    
    return True
def trustLevel(trustint):
    """
    Returns the written trust level based on its numerical value
    :param trustnum: The trust integer to convert to written form
    :return: The written form for the specified trust integet
    """
    if trustint == TrustLevel.KNOWN_TRUSTED_INSTALLER:
        return "Known Trusted Installer"
    elif trustint >= TrustLevel.KNOWN_TRUSTED:
        return "Known Trusted"
    elif trustint >= TrustLevel.MOST_LIKELY_TRUSTED:
        return "Most Likely Trusted"
    elif trustint >= TrustLevel.MIGHT_BE_TRUSTED:
        return "Might Be Trusted"
    elif trustint >= TrustLevel.UNKNOWN:
        return "Unknown"
    elif trustint >= TrustLevel.MIGHT_BE_MALICIOUS:
        return "Might Be Malicious"
    elif trustint >= TrustLevel.MOST_LIKELY_MALICIOUS:
        return "Most Likely Malicious"
    elif trustint >= TrustLevel.KNOWN_MALICIOUS:
        return "Known Malicious"
    else:
        return "Not Set"

def doGetSystems(btn):
    #This function request a systems query with any system given a hash.
    #MAR supports MD5 and SHA1

    page_size = 5
    strHash=str(chatWin.getEntry("TIE_Hash"))

    mar_client=MarClient(client)

    results_context = mar_client.search(
                            projections=[{
                                ProjectionConstants.NAME: "HostInfo",
                                ProjectionConstants.OUTPUTS: ["hostname", "ip_address"]
                                },
                                {
                                ProjectionConstants.NAME: "Files",
                                ProjectionConstants.OUTPUTS: ["full_name"]
                                }],
                            conditions={
                                ConditionConstants.OR: [{
                                    ConditionConstants.AND: [{
                                        ConditionConstants.COND_NAME: "Files",
                                        ConditionConstants.COND_OUTPUT: "md5",
                                        ConditionConstants.COND_OP: OperatorConstants.EQUALS,
                                        ConditionConstants.COND_VALUE: strHash
                                        }]
                                },
                                {
                                    ConditionConstants.AND: [{
                                        ConditionConstants.COND_NAME: "Files",
                                        ConditionConstants.COND_OUTPUT: "sha1",
                                        ConditionConstants.COND_OP: OperatorConstants.EQUALS,
                                        ConditionConstants.COND_VALUE: strHash
                                        }]
                                }]
                        })
    if results_context.has_results:
        for index in range(0, results_context.result_count, page_size):
            # Retrieve the next page of results (sort by process name, ascending)
            results = results_context.get_results(index, page_size,
                                                  sort_by="HostInfo|ip_address",
                                                  sort_direction=SortConstants.ASC)
            # Display items in the current page
            logger.info("Page: " + str((index/page_size)+1))
            for item in results[ResultConstants.ITEMS]:
                strResults = str("{}({}):   {}".format(item[ResultConstants.ITEM_OUTPUT]["HostInfo|hostname"], item[ResultConstants.ITEM_OUTPUT]["HostInfo|ip_address"], item[ResultConstants.ITEM_OUTPUT]["Files|full_name"] ))

                logger.info(strResults)

                chatWin.setTextArea("HashResults", strResults + "\n", False)
        chatWin.setTextArea("HashResults", "ActiveResponse Results\n", False)
    else:
        chatWin.setTextArea("HashResults", "No MAR results for search.", False)
        logger.info("No MAR results for search.")
                                    


def doReputation(btn):

    global hashType

    strHash=str(chatWin.getEntry("TIE_Hash"))
    logger.info( "Getting reputation data for {0}.".format(str(strHash)))

    #Get all TIE based reputation data associated with a given hash
    tie_client = TieClient(client)

    reputations_dict = {}

    #Request raw json reputation results
    if hashType=="md5":
        reputations_dict = tie_client.get_file_reputation({ HashType.MD5: strHash })
    elif hashType=="sha1":
        reputations_dict = tie_client.get_file_reputation({ HashType.SHA1: strHash })
    elif hashType=="sha256":
        reputations_dict = tie_client.get_file_reputation({ HashType.SHA256: strHash })

    #debug
    logger.info("Raw TIE results for hash type " + hashType + ": " + json.dumps(reputations_dict, sort_keys=True, indent=4, separators=(',', ': ')))
    
    #Start building repputation output for writing to the results TextArea
    
    strResults = parseTIEResults(reputations_dict)

    #chatWin.setTextArea("TIEResults", json.dumps(reputations_dict, sort_keys=True, indent=4, separators=    (',', ': ')), False)
    chatWin.setTextArea("HashResults", strResults, False)
    return True


def parseTIEResults(reputations_dict):
    proc_result = {}
    tiekey = 0
    strtiekey = str(tiekey)
    strResult = ""
    
    # Display the Global Threat Intelligence 
    if FileProvider.GTI in reputations_dict:
        gti_rep = reputations_dict[FileProvider.GTI]
        proc_result[strtiekey]={}
        proc_result[strtiekey]['title']="Global Threat Intelligence (GTI) Test Date:"
        proc_result[strtiekey]['value']= EpochMixin.to_localtime_string(gti_rep[ReputationProp.CREATE_DATE])
        strResult += proc_result[strtiekey]['title'] + proc_result[strtiekey]['value'] + "\n"
        tiekey += 1
        strtiekey = str(tiekey)

        #Get GTI Trust Level
        proc_result[strtiekey]={}
        proc_result[strtiekey]['title']="Global Threat Intelligence (GTI) trust level:"
        trustValue=gti_rep[ReputationProp.TRUST_LEVEL]
        proc_result[strtiekey]['value']= trustLevel(trustValue)
        strResult += proc_result[strtiekey]['title'] + proc_result[strtiekey]['value'] + "\n"
        tiekey += 1
        strtiekey = str(tiekey)

    # Display the Enterprise reputation information
    if FileProvider.ENTERPRISE in reputations_dict:
        ent_rep = reputations_dict[FileProvider.ENTERPRISE]

        # Retrieve the enterprise reputation attributes
        ent_rep_attribs = ent_rep[ReputationProp.ATTRIBUTES]

        #Get Enterprise Trust Level
        proc_result[strtiekey]={}
        proc_result[strtiekey]['title']="Enterprise trust level:"
        trustValue=ent_rep[ReputationProp.TRUST_LEVEL]
        proc_result[strtiekey]['value']= trustLevel(trustValue)
        strResult += proc_result[strtiekey]['title'] + proc_result[strtiekey]['value'] + "\n"
        tiekey += 1
        strtiekey = str(tiekey)


        # Display prevalence (if it exists)
        if FileEnterpriseAttrib.PREVALENCE in ent_rep_attribs:
            proc_result[strtiekey]={}
            proc_result[strtiekey]['title'] = "Enterprise prevalence:"
            proc_result[strtiekey]['value'] =  ent_rep_attribs[FileEnterpriseAttrib.PREVALENCE]
            strResult += proc_result[strtiekey]['title'] + proc_result[strtiekey]['value'] + "\n"
            tiekey += 1
            strtiekey = str(tiekey)

        # Display first contact date (if it exists)
        if FileEnterpriseAttrib.FIRST_CONTACT in ent_rep_attribs:
            proc_result[strtiekey]={}
            proc_result[strtiekey]['title'] =  "First contact: "
            proc_result[strtiekey]['value'] =  FileEnterpriseAttrib.to_localtime_string(ent_rep_attribs[FileEnterpriseAttrib.FIRST_CONTACT])
            strResult += proc_result[strtiekey]['title'] + proc_result[strtiekey]['value'] + "\n"
            tiekey += 1
            strtiekey = str(tiekey)

 
 #These are lookup conversions for the ATD trust_score
    valueDict = {}
    valueDict['-1']="Known Trusted"
    valueDict['0']="Most Likely Trusted"
    valueDict['1']="Might Be Trusted"
    valueDict['2']="Unknown"
    valueDict['3']="Might Be Malicious"
    valueDict['4']="Most Likely Malicious"
    valueDict['5']="Known Malicious"
    valueDict['-2']="Not Set"


    # Display the ATD reputation information
    if FileProvider.ATD in reputations_dict:
        atd_rep = reputations_dict[FileProvider.ATD]

        # Retrieve the ATD reputation attributes
        atd_rep_attribs = atd_rep[ReputationProp.ATTRIBUTES]

        proc_result[strtiekey]={}
        proc_result[strtiekey]['title'] = "ATD Test Date: "
        proc_result[strtiekey]['value']= EpochMixin.to_localtime_string(atd_rep[ReputationProp.CREATE_DATE])
        strResult += proc_result[strtiekey]['title'] + proc_result[strtiekey]['value'] + "\n"
        tiekey += 1
        strtiekey = str(tiekey)

        # Display GAM Score (if it exists)
        if AtdAttrib.GAM_SCORE in atd_rep_attribs:
            proc_result[strtiekey]={}
            proc_result[strtiekey]['title'] = "ATD Gateway AntiMalware Score: "
            proc_result[strtiekey]['value'] =  valueDict[atd_rep_attribs[AtdAttrib.GAM_SCORE]]
            strResult += proc_result[strtiekey]['title'] + proc_result[strtiekey]['value'] + "\n"
            tiekey += 1
            strtiekey = str(tiekey)

        # Display AV Engine Score (if it exists)
        if AtdAttrib.AV_ENGINE_SCORE in atd_rep_attribs:
            proc_result[strtiekey]={}
            proc_result[strtiekey]['title'] = "ATD AV Engine Score: "
            proc_result[strtiekey]['value'] = valueDict[atd_rep_attribs[AtdAttrib.AV_ENGINE_SCORE]]
            strResult += proc_result[strtiekey]['title'] + proc_result[strtiekey]['value'] + "\n"
            tiekey += 1
            strtiekey = str(tiekey)

        # Display Sandbox Score (if it exists)
        if AtdAttrib.SANDBOX_SCORE in atd_rep_attribs:
            proc_result[strtiekey]={}
            proc_result[strtiekey]['title'] = "ATD Sandbox Score: "
            proc_result[strtiekey]['value'] = valueDict[atd_rep_attribs[AtdAttrib.SANDBOX_SCORE]]
            strResult += proc_result[strtiekey]['title'] + proc_result[strtiekey]['value'] + "\n"
            tiekey += 1
            strtiekey = str(tiekey)

        # Display Verdict (if it exists)
        if AtdAttrib.VERDICT in atd_rep_attribs:
            proc_result[strtiekey]={}
            proc_result[strtiekey]['title'] = "ATD Verdict: "
            proc_result[strtiekey]['value'] = valueDict[atd_rep_attribs[AtdAttrib.VERDICT]]
            strResult += proc_result[strtiekey]['title'] + proc_result[strtiekey]['value'] + "\n"
            tiekey += 1
            strtiekey = str(tiekey)

    return strResult
    #End Function



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

investigateMenus = ["Hash Investigation"]
chatWin.addMenuList("Investigate", investigateMenus, menuPress)

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
                    #chatWin.updateListItems("listUsers",usernames)
                    # Updated to account for deprecated function
                    chatWin.updateListBox("listUsers",usernames)

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
                    chatWin.updateListBox("listUsers",usernames)

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

    #Build SubWindows for the chatWin application
    chatWin.startSubWindow("Hash Investigation")

    chatWin.addLabel("TIE_Label", "MD5/SHA1/SHA256", 0,0)

    chatWin.addValidationEntry("TIE_Hash",0,1)
    chatWin.setEntryInvalid("TIE_Hash")
    chatWin.setEntryChangeFunction("TIE_Hash", validateHash)
    chatWin.setEntryWidths("TIE_Hash", 78)

    chatWin.addButton("Get Reputations", doReputation, 0,2 )
    chatWin.disableButton("Get Reputations")

    chatWin.addButton("ActiveResponse Get Systems", doGetSystems, 1,2 )
    chatWin.disableButton("ActiveResponse Get Systems")

    chatWin.addScrolledTextArea("HashResults",2,0,3)
    chatWin.setTextAreaWidth("HashResults", 120)
    chatWin.setTextAreaHeight("HashResults", 20)

    chatWin.stopSubWindow()



    chatWin.go("chatWin")
