# Copyright (c) <2013>, Psyop
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


_sianchor = None

import sys
import platform
from PySide import QtGui, QtCore

# Running exec_ on a QApp while in softimage is a big no no...chaos ensues.
# We'll duck punch in this simple method to replace it which raises an exception.
def qapp_exec_disallowed(*args, **kwargs):
    raise AttributeError("Running exec_ on a qapp is disallowed.")
QtCore.QCoreApplication.exec_ = qapp_exec_disallowed
QtGui.QApplication.exec_ = qapp_exec_disallowed

ANCHOR_NAME = "QtSoftimageAnchor"


class AnchorWidget(QtGui.QWidget):
    """Widget class for the Qt softimage anchor."""
    def event(self, event):
        # Convert all child widgets to top-level windows.
        # The anchor widget should never actually be shown.
        if event.type() == QtCore.QEvent.ChildAdded:
            event.child().setWindowFlags(QtCore.Qt.Window)
            return True
        return super(AnchorWidget, self).event(event)


def _ensure_qapp_exists():
    """Create a QApplication instance if none exists."""
    if not QtGui.QApplication.instance():
        app = QtGui.QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)


def _win32_get_application_window_handle():
    """Equivalent to the Desktop::GetApplicationWindowHandle C++ API method."""
    import win32api
    import win32gui

    # Object Model has no equivalent to Desktop::GetApplicationWindowHandle
    # (Not that I'm aware of, anyway)
    #
    # Instead, we enumerate all top level windows in the current thread,
    # attempting to find one which appears to be the main Softimage window.
    # Currently this is based on the window title (The window style might give
    # some clues as well. The window class name is unpredictable).

    class _FindWindow(object):
        def __init__(self, predicate):
            self.predicate = predicate
            self.results = []

        def __call__(self, hwnd, extra):
            if self.predicate(hwnd):
                self.results.append(hwnd)

    predicate = lambda hwnd: win32gui.GetWindowText(hwnd).startswith("Autodesk Softimage")
    finder = _FindWindow(predicate)

    win32gui.EnumThreadWindows(win32api.GetCurrentThreadId(), finder, None)
    return finder.results[0] if finder.results else None


def _generic_install_anchor(widget):
    """Generic fallback method for floating windows."""
    widget.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)


def _win32_install_anchor(widget):
    """Window parenting based on Jo Benayoun and Steve Caron's QtSoftimage C++ plugin."""
    import win32api
    import win32gui
    import ctypes

    xsi_hwnd = _win32_get_application_window_handle()
    if xsi_hwnd:
        # QWidget.winId method of PySide returns a PyCObject.
        # This is cast to an integer using ctypes.
        ctypes.pythonapi.PyCObject_AsVoidPtr.restype = ctypes.c_void_p
        ctypes.pythonapi.PyCObject_AsVoidPtr.argtypes = [ ctypes.py_object ]
        hwnd = ctypes.pythonapi.PyCObject_AsVoidPtr(widget.winId())

        # Reparent the QWidget to the main Softimage window.
        GWL_STYLE = -16
        WS_CHILD = 0x40000000
        win32api.SetWindowLong(hwnd, GWL_STYLE, WS_CHILD)
        win32gui.SetParent(hwnd, xsi_hwnd)
    else:
        # Couldn't get Softimage main window handle
        # Fall back to the generic method.
        _generic_install_anchor(widget)


def get_anchor():
    """Get a top-level QWidget suitable for parenting other widgets to.

    This also ensures that a QApplication instance is created.
    """
    global _sianchor

    _ensure_qapp_exists()

    if not _sianchor:
        _sianchor = AnchorWidget()
        _sianchor.setObjectName(ANCHOR_NAME)
        _sianchor.setWindowTitle(ANCHOR_NAME)

        # Make the widget float on top of the main window, using the best
        # method available for the current platform.
        if platform.system() == "Windows":
            _win32_install_anchor(_sianchor)
        else:
            _generic_install_anchor(_sianchor)

    return _sianchor


def destroy_anchor():
    """Destroy the top-level anchor widget.

    If the widget does not yet exist, this function has no effect.
    The running QApplication instance will not be destroyed.
    """
    global _sianchor
    if _sianchor is not None:
        _sianchor.close()
    _sianchor = None
