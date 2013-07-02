# Copyright (c) <2011>, Steven Caron <steven@steven-caron.com>
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <organization> nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from PySide.QtCore import QObject
from PySide.QtCore import Signal

from win32com.client import Dispatch as disp
from win32com.client import constants as C
si = disp('XSI.Application')

EVENT_MAPPING = {
    #pyqtsignal : softimage event
    "siActivate" : "QtEvents_Activate",
    "siFileExport" : "QtEvents_FileExport",
    "siFileImport" : "QtEvents_FileImport",
    "siCustomFileExport" : "QtEvents_CustomFileExport",
    "siCustomFileImport" : "QtEvents_CustomFileImport",

    "siRenderFrame" : "QtEvents_RenderFrame",
    "siRenderSequence" : "QtEvents_RenderSequence",
    "siRenderAbort" : "QtEvents_RenderAbort",
    "siPassChange" : "QtEvents_PassChange",

    "siSceneOpen" : "QtEvents_SceneOpen",
    "siSceneSaveAs" : "QtEvents_SceneSaveAs",
    "siSceneSave" : "QtEvents_SceneSave",
    "siChangeProject" : "QtEvents_ChangeProject",

    "siConnectShader" : "QtEvents_ConnectShader",
    "siDisconnectShader" : "QtEvents_DisconnectShader",
    "siCreateShader" : "QtEvents_CreateShader",

    "siDragAndDrop" : "QtEvents_DragAndDrop",

    "siObjectAdded" : "QtEvents_ObjectAdded",
    "siObjectRemoved" : "QtEvents_ObjectRemoved",

    "siSelectionChange" : "QtEvents_SelectionChange",

    "siSourcePathChange" : "QtEvents_SourcePathChange",

    "siValueChange" : "QtEvents_ValueChange",
}

class SISignals( QObject ):
    """
    class for mapping softimage events to pyqt signals
    not all context attributes are passed as signal arguments, add more as needed
    currently all signals are expected to be 'siOnEnd' versions of softimage events
    """

    # add more pyqtsignals that map to softimage events here
    siActivate = Signal(bool) # siOnActivate

    siFileExport = Signal(str) # siOnEndFileExport
    siFileImport = Signal(str) # siOnEndFileImport
    siCustomFileExport = Signal(str) # siOnCustomFileExport
    siCustomFileImport = Signal(str) # siOnCustomFileImport

    siRenderFrame = Signal(str,int) # siOnEndFrame
    siRenderSequence = Signal(str,int) # siOnEndSequence
    siRenderAbort = Signal(str,int) # siOnRenderAbort
    siPassChange = Signal(str) # siOnEndPassChange

    siSceneOpen = Signal(str) # siOnEndSceneOpen
    siSceneSaveAs = Signal(str) # siOnEndSceneSaveAs
    siSceneSave = Signal(str) # siOnEndSceneSave2
    siChangeProject = Signal(str) # siOnChangeProject

    siConnectShader = Signal(str,str) # siOnConnectShader
    siDisconnectShader = Signal(str,str) # siOnDisconnectShader
    siCreateShader = Signal(str,str) # siOnCreateShader

    siDragAndDrop = Signal(str) # siOnDragAndDrop

    siObjectAdded = Signal(list) # siOnObjectAdded
    siObjectRemoved = Signal(list) # siOnObjectRemoved

    siSelectionChange = Signal(int) # siOnSelectionChange

    siSourcePathChange = Signal(str) # siOnSourcePathChange

    siValueChange = Signal(str) # siOnValueChange

    def __init__(self):
        QObject.__init__(self)
        self.setObjectName( "siSignals" )

signals = SISignals()

def muteSIEvent( event, state = True ):
    events = si.EventInfos
    event = events( EVENT_MAPPING[event] )
    if si.ClassName( event ) == "EventInfo":
        event.Mute = state
