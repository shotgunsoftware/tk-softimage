import sys
import win32com.client
from win32com.client import constants
xsi = win32com.client.Dispatch('XSI.Application').Application

from PySide import QtCore, QtGui

g_rdoSIAnchor = None


def XSILoadPlugin( in_reg ):
    in_reg.Author = "Julien Dubuisson"
    in_reg.Name = "rdoQtForSoftimage"
    in_reg.Major = 1
    in_reg.Minor = 0

    in_reg.RegisterCommand("rdoGetQtSoftimageAnchor","rdoGetQtSoftimageAnchor")
    in_reg.RegisterCommand("rdoCloseQtSoftimageAnchor","rdoCloseQtSoftimageAnchor")
    in_reg.RegisterCommand("rdoKillQtSoftimageAnchor","rdoKillQtSoftimageAnchor")
    in_reg.RegisterCommand("rdoStartQtTimer","rdoStartQtTimer")
    in_reg.RegisterCommand("rdoStopQtTimer","rdoStopQtTimer")

    in_reg.RegisterTimerEvent( "rdoQtTimer", 20, 0 );

    return True

def XSIUnloadPlugin( in_reg ):
    strPluginName = in_reg.Name
    xsi.LogMessage(str(strPluginName) + str(" has been unloaded."),constants.siVerbose)

    from Qt.anchor import destroy_anchor
    destroy_anchor()

    return True

def rdoGetQtSoftimageAnchor_Init( in_ctxt ):
    oCmd = in_ctxt.Source
    oCmd.Description = ""
    oCmd.ReturnValue = True

    return True

def rdoGetQtSoftimageAnchor_Execute(  ):
    xsi.LogMessage("rdoGetQtSoftimageAnchor_Execute called",constants.siVerbose)
    if not QtCore.QCoreApplication.instance():
        QtGui.QApplication(sys.argv)

    xsi.EventInfos( "rdoQtTimer" ).Mute = False

    from Qt.anchor import get_anchor
    anchor = get_anchor()

    # Assuming current versions of CPython, this can be converted back to a
    # python object using ctypes.cast. In order to use shiboken, I believe
    # we should be using shiboken.getCppPointer here (since the addresses of
    # the PyObject and underlying QWidget are different).
    return id(anchor)

def rdoKillQtSoftimageAnchor_Init( in_ctxt ):
    oCmd = in_ctxt.Source
    oCmd.Description = ""
    oCmd.ReturnValue = True

    return True

def rdoKillQtSoftimageAnchor_Execute(  ):
    global g_rdoSIAnchor
    xsi.LogMessage("rdoGetQtSoftimageAnchor_Execute called",constants.siVerbose)

    from Qt.anchor import destroy_anchor
    destroy_anchor()

    # destroy_anchor doesn't shut down the QApplication.
    # Do that here to preserve current behavior.
    if QtCore.QCoreApplication.instance():
        QtCore.QCoreApplication.instance().exit()
        xsi.EventInfos( "rdoQtTimer" ).Mute = True

    return True

def rdoCloseQtSoftimageAnchor_Init( in_ctxt ):
    oCmd = in_ctxt.Source
    oCmd.Description = ""
    oCmd.ReturnValue = True

    return True

def rdoCloseQtSoftimageAnchor_Execute(  ):
    global g_rdoSIAnchor
    xsi.LogMessage("rdoCloseQtSoftimageAnchor_Execute called",constants.siVerbose)

    from Qt.anchor import get_anchor
    anchor = get_anchor()
    anchor.close()

    return True

def rdoStartQtTimer_Init( in_ctxt ):
    oCmd = in_ctxt.Source
    oCmd.Description = ""
    oCmd.ReturnValue = True

    return True

def rdoStartQtTimer_Execute(  ):
    xsi.LogMessage("rdoStartQtTimer_Execute called",constants.siVerbose)
    xsi.EventInfos( "rdoQtTimer" ).Mute = False
    return True

def rdoStopQtTimer_Init( in_ctxt ):
    oCmd = in_ctxt.Source
    oCmd.Description = ""
    oCmd.ReturnValue = True

    return True

def rdoStopQtTimer_Execute(  ):
    xsi.LogMessage("rdoStopQtTimer_Execute called",constants.siVerbose)
    xsi.EventInfos( "rdoQtTimer" ).Mute = True
    return True

def rdoQtTimer_OnEvent( in_ctxt ):
    if QtCore.QCoreApplication.instance():
        QtCore.QCoreApplication.processEvents()