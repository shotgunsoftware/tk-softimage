from PySide import QtGui, QtCore

import xml.etree.ElementTree as xml
from cStringIO import StringIO

import anchor
import win32com.client
xsi = win32com.client.Dispatch('XSI.Application').Application

qt_dialogs_storage = []

def loadUiType(uiFile):
    """
    Pyside lacks the "loadUiType" command, so we have to convert the ui file to py code in-memory first
    and then execute it in a special frame to retrieve the form_class.
    http://nathanhorne.com/?p=451
    """
    import pysideuic

    parsed = xml.parse(uiFile)
    widget_class = parsed.find('widget').get('class')
    form_class = parsed.find('class').text

    f = open(uiFile, 'r')
    if f:
        o = StringIO()
        frame = {}

        pysideuic.compileUi(f, o, indent=0)
        pyc = compile(o.getvalue(), '<string>', 'exec')
        exec pyc in frame

        #Fetch the base_class and form class based on their type in the xml from designer
        form_class = frame['Ui_%s'%form_class]
        base_class = eval('QtGui.%s'%widget_class)
    return form_class, base_class

def getQtSoftimageAnchor():
    xsi.rdoStartQtTimer()
    return anchor.get_anchor()

def store_qt_dialog(dialog):
    global qt_dialogs_storage
    qt_dialogs_storage.append(dialog)
