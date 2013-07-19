# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Implements the Softimage Engine in Tank.
"""

import win32com.client
from win32com.client import constants

import tank

null = None
false = 0
true = 1

def XSILoadPlugin( in_reg ):
    in_reg.Author = "Tank"
    in_reg.Name = "TankMenu"
    in_reg.Major = 1
    in_reg.Minor = 0

    # Make menu dynamic in order to support enable_callback functions
    in_reg.RegisterMenu(constants.siMenuMainTopLevelID, "Tank", false, true)

    #RegistrationInsertionPoint - do not remove this line

    return true

def XSIUnloadPlugin( in_reg ):
    strPluginName = in_reg.Name
    Application.LogMessage(str(strPluginName) + str(" has been unloaded."),constants.siVerbose)
    return true

#########################################################################################################################

def Tank_Init( in_ctxt ):
    try:
        # Engine initialization might not be completed yet, so we can't rely
        # on tank.platform.current_engine()
        menu_generator = tank.platform.__si_menu_generator__
    except AttributeError:
        Application.LogMessage("TankMenu_Init() -- No supported Tank engine is running!", 8)
        return false
    else:
        menu_generator.create_menu(in_ctxt.Source, globals())
        return true
