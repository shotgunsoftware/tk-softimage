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
Implements the Softimage Engine for the Shotgun Pipeline Toolkit.
"""

import sys
import os

import sgtk
from sgtk.platform import Engine

import win32com
from win32com.client import Dispatch, constants
Application = Dispatch("XSI.Application").Application
XSIUIToolkit = Dispatch("XSI.UIToolkit")

class SoftimageEngine(Engine):

    ##########################################################################################
    # init and destroy

    def init_engine(self):
        """
        Called when the engine is being initialized
        """
        
        # check this is a version of Softimage that we support:
        if sys.platform != "win32":
            self.log_error("The tk-softimage engine is currently only supported on Windows!")    
            return
        
        # determine if this is a tested version:
        is_certified_version = False
        version_str = Application.version()
        version_parts = version_str.split(".")
        if version_parts and version_parts[0].isnumeric():
            version_major = int(version_parts[0])
            if (version_major >= 10     # >= Softimage 2012
                and version_major <= 11 # <= Softimage 2013
                ): 
                is_certified_version = True
                
        if not is_certified_version:
            # show a warning:
            msg = ("The Shotgun Pipeline Toolkit has not yet been fully tested with Softimage %s. "
                   "You can continue to use the Toolkit but you may experience bugs or "
                   "instability.  Please report any issues you see to toolkitsupport@shotgunsoftware.com" 
                   % (version_str))
            
            if self.has_ui and "SGTK_SOFTIMAGE_VERSION_WARNING_SHOWN" not in os.environ:
                # have to call RedrawUI() otherwise Softimage will crash!
                Application.Desktop.RedrawUI()
                XSIUIToolkit.MsgBox("Warning - Shotgun Pipeline Toolkit!\n\n%s" % msg)
                os.environ["SGTK_SOFTIMAGE_VERSION_WARNING_SHOWN"] = "1"
                
            self.log_warning(msg)
            
        # keep handles to all qt dialogs to help GC
        self.__created_qt_dialogs = []

        # Set the Softimage project based on config
        self._set_project()
        
        # menu:
        self._menu = None
        tk_softimage = self.import_module("tk_softimage")
        self._menu_generator = tk_softimage.MenuGenerator(self)
        self._shotgun_plugin_path = os.path.join(self.disk_location, "resources", "plugins", "shotgun", "Application", "Plugins")
        
        
    def destroy_engine(self):
        """
        Called when engine is destroyed
        """
        self.log_debug("%s: Destroying..." % self)

        # clean up UI:
        if self.has_ui:
            if self._menu:
                # close any torn-off menus:
                self._menu.close_torn_off_menus()
        
            # Unload the menu plugin
            Application.UnloadPlugin(os.path.join(self._shotgun_plugin_path, "menu.py"))

            # unload the qtevents plugin
            Application.UnloadPlugin(os.path.join(self._shotgun_plugin_path, "qt_events.py"))

    @property
    def has_ui(self):
        """
        Detect and return if Softimage is running in batch mode
        """
        return Application.Interactive

    def post_app_init(self):
        """
        Called when all apps have initialized
        """
        if self.has_ui:
            # ensure we have a QApplication
            from sgtk.platform.qt import QtGui
            if not QtGui.QApplication.instance():
                self.log_debug("Creating main QApplication and setting up style sheet!")
                QtGui.QApplication.setStyle("cleanlooks")
                qt_app = QtGui.QApplication([])
                qt_app.setQuitOnLastWindowClosed(False)
                
                # and set up the dark style sheet:
                css_file = os.path.join(self.disk_location, "resources", "dark.css")
                f = open(css_file)
                css = f.read()
                f.close()
                qt_app.setStyleSheet(css)
            
            # Re-load the menu plugin
            Application.UnloadPlugin(os.path.join(self._shotgun_plugin_path, "menu.py"))
            Application.LoadPlugin(os.path.join(self._shotgun_plugin_path, "menu.py"))
            
            Application.UnloadPlugin(os.path.join(self._shotgun_plugin_path, "qt_events.py"))
            Application.LoadPlugin(os.path.join(self._shotgun_plugin_path, "qt_events.py"))

    def populate_shotgun_menu(self, menu):
        """
        Use the menu generator to populate the Shotgun menu
        """
        self._menu = menu
        self._menu_generator.create_menu(self._menu)

    ##########################################################################################
    # logging

    def log_debug(self, msg):
        if self.get_setting("debug_logging", False):
            Application.LogMessage("Shotgun: %s" % msg, constants.siInfo)

    def log_info(self, msg):
        Application.LogMessage("Shotgun: %s" % msg, constants.siInfo)

    def log_warning(self, msg):
        Application.LogMessage("Shotgun: %s" % msg, constants.siWarning)

    def log_error(self, msg):
        import traceback
        tb = traceback.print_exc()
        if tb:
            msg = tb+"\n"+msg
        Application.LogMessage("Shotgun: %s" % msg, constants.siError)

    ##########################################################################################
    # scene and project management

    def _set_project(self):
        """
        Set the softimage project
        """
        setting = self.get_setting("template_project")
        if setting is None:
            return

        tmpl = self.sgtk.templates.get(setting)
        fields = self.context.as_template_fields(tmpl)
        proj_path = tmpl.apply_fields(fields)
        self.log_info("Setting Softimage project to '%s'" % proj_path)

        try:
            # test to see if the project has already been set to this path:
            if (Application.ActiveProject.Path 
                and os.path.normpath(Application.ActiveProject.Path).lower() == os.path.normpath(proj_path).lower()):
                # project is already set to this path so no need to do anything!
                return
            
            # make sure the project exists:
            created_proj = Application.CreateProject(proj_path)
            if not created_proj:
                raise

            # and set it:
            Application.ActiveProject = proj_path
        except:
            self.log_error("Error setting Softimage Project: %s" % proj_path)

    ##########################################################################################
    # pyside / qt

    def _define_qt_base(self):
        """
        check for pyside then pyqt
        """
        # proxy class used when QT does not exist on the system.
        # this will raise an exception when any QT code tries to use it
        class QTProxy(object):                        
            def __getattr__(self, name):
                raise sgtk.TankError("Looks like you are trying to run an App that uses a QT "
                                     "based UI, however the Softimage engine could not find a PyQt "
                                     "or PySide installation in your python system path. We " 
                                     "recommend that you install PySide if you want to "
                                     "run UI applications from within Softimage.")
        
        base = {"qt_core": QTProxy(), "qt_gui": QTProxy(), "dialog_base": None}
        self._has_ui = False
        
        if not self._has_ui:
            try:
                from PySide import QtCore, QtGui
                import PySide

                # tell QT to interpret C strings as utf-8
                utf8 = QtCore.QTextCodec.codecForName("utf-8")
                QtCore.QTextCodec.setCodecForCStrings(utf8)
                
                base["qt_core"] = QtCore
                base["qt_gui"] = QtGui
                base["dialog_base"] = QtGui.QDialog
                self.log_debug("Successfully initialized PySide %s located in %s." % (PySide.__version__, PySide.__file__))
                self._has_ui = True
            except ImportError:
                pass
            except Exception, e:
                self.log_warning("Error setting up pyside. Pyside based UI support will not "
                                 "be available: %s" % e)
        
        if not self._has_ui:
            try:
                from PyQt4 import QtCore, QtGui
                import PyQt4
                
                # tell QT to interpret C strings as utf-8
                utf8 = QtCore.QTextCodec.codecForName("utf-8")
                QtCore.QTextCodec.setCodecForCStrings(utf8)                
                
                # hot patch the library to make it work with pyside code
                QtCore.Signal = QtCore.pyqtSignal   
                QtCore.Property = QtCore.pyqtProperty             
                base["qt_core"] = QtCore
                base["qt_gui"] = QtGui
                base["dialog_base"] = QtGui.QDialog
                self.log_debug("Successfully initialized PyQt %s located in %s." % (QtCore.PYQT_VERSION_STR, PyQt4.__file__))
                self._has_ui = True
            except ImportError:
                pass
            except Exception, e:
                self.log_warning("Error setting up PyQt. PyQt based UI support will not "
                                 "be available: %s" % e)
                
        if not self._has_ui:
            # lets try the version of PySide included with the engine:
            pyside_root = None            
            if sys.platform == "win32":
                if sys.version_info[0] == 2 and sys.version_info[1] == 6:
                    pyside_root = os.path.join(self.disk_location, "resources","pyside120_py26_qt484_win64")
                elif sys.version_info[0] == 2 and sys.version_info[1] == 7:
                    pyside_root = os.path.join(self.disk_location, "resources","pyside120_py27_qt485_win64")
            else:
                pass

            if pyside_root:
                self.log_debug("Attempting to import PySide from %s" % pyside_root)
                if pyside_root not in sys.path:
                    sys.path.append(pyside_root)

                try:
                    from PySide import QtCore, QtGui
                    import PySide
    
                    # tell QT to interpret C strings as utf-8
                    utf8 = QtCore.QTextCodec.codecForName("utf-8")
                    QtCore.QTextCodec.setCodecForCStrings(utf8)
                    
                    base["qt_core"] = QtCore
                    base["qt_gui"] = QtGui
                    base["dialog_base"] = QtGui.QDialog
                    self.log_debug("Successfully initialized PySide %s located in %s." % (PySide.__version__, PySide.__file__))
                    self._has_ui = True
                except ImportError:
                    pass
                except Exception, e:
                    self.log_warning("Error setting up PySide. Pyside based UI support will not "
                                     "be available: %s" % e)
        return base

    def _create_dialog(self, title, bundle, widget_class, *args, **kwargs):
        """
        Create the standard Toolkit dialog, with ownership assigned to the main photoshop
        application window if possible.

        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget_class: The class of the UI to be constructed. This must derive from QWidget.

        Additional parameters specified will be passed through to the widget_class constructor.

        :returns: the created widget_class instance
        """
        from sgtk.platform.qt import tankqdialog

        # first construct the widget object
        obj = widget_class(*args, **kwargs)

        # get the parent for the widget to use:
        if not hasattr(self, "_qt_parent_widget"):
            tk_softimage = self.import_module("tk_softimage")
            self._qt_parent_widget = tk_softimage.get_qt_parent_window()
        
        # now construct the dialog:
        dialog = tankqdialog.TankQDialog(title, bundle, obj, self._qt_parent_widget)
        
        # keep a reference to all created dialogs to make GC happy
        self.__created_qt_dialogs.append(dialog)
        
        # watch for the dialog closing so that we can clean up
        # (AD) - experimental!
        # dialog.dialog_closed.connect(self._on_dialog_closed)

        return dialog, obj
    
    def _on_dialog_closed(self, dlg):
        """
        """
        if dlg in self.__created_qt_dialogs:
            # don't need to track this dialog any longer
            self.__created_qt_dialogs.remove(dlg)
            
        # detach the widget - there may still be other 
        # references to it somewhere
        dlg.detach_widget()
        
        from pprint import pprint
        import gc
        import sys
        print "Dialog has %s references:" % sys.getrefcount(dlg)
        pprint(gc.get_referrers(dlg))
        
        # finally, let Qt know this dialog can be deleted
        dlg.deleteLater()  
    
    def show_dialog(self, title, bundle, widget_class, *args, **kwargs):
        """
        Shows a non-modal dialog window in a way suitable for this engine.
        The engine will attempt to parent the dialog nicely to the host application.

        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget_class: The class of the UI to be constructed. This must derive fromzQWidget.

        Additional parameters specified will be passed through to the widget_class constructor.

        :returns: the created widget_class instance
        """
        debug_force_modal = False  # debug switch for testing modal dialog
        if debug_force_modal:
            status, obj = self.show_modal(title, bundle, widget_class, *args, **kwargs)
            return obj
        else:
            dialog, obj = self._create_dialog(title, bundle, widget_class, *args, **kwargs)
            dialog.show()
            return obj    
    
    def show_modal(self, title, bundle, widget_class, *args, **kwargs):
        """
        Shows a modal dialog window in a way suitable for this engine. The engine will attempt to
        integrate it as seamlessly as possible into the host application. This call is blocking
        until the user closes the dialog.

        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget_class: The class of the UI to be constructed. This must derive from QWidget.

        Additional parameters specified will be passed through to the widget_class constructor.

        :returns: (a standard QT dialog status return code, the created widget_class instance)
        """
        from PySide import QtGui
        
        dialog, obj = self._create_dialog(title, bundle, widget_class, *args, **kwargs)

        status = QtGui.QDialog.Rejected
        if sys.platform == "win32":

            # when we show a modal dialog, the application should be disabled.
            # However, because the QApplication doesn't have control over the
            # main Softimage window we have to do this ourselves...
            import win32api, win32gui
            tk_softimage = self.import_module("tk_softimage")

            foreground_window = None
            saved_state = []
            try:
                # find all windows and save enabled state:
                foreground_window = win32gui.GetForegroundWindow()
                #self.log_debug("Disabling main application windows before showing modal dialog")
                found_hwnds = tk_softimage.find_windows(thread_id = win32api.GetCurrentThreadId(), stop_if_found=False)
                for hwnd in found_hwnds:
                    enabled = win32gui.IsWindowEnabled(hwnd)
                    saved_state.append((hwnd, enabled))
                    if enabled:
                        # disable the window:
                        win32gui.EnableWindow(hwnd, False)

                # show dialog:
                status = dialog.exec_()
                
            except Exception, e:
                self.log_error("Error showing modal dialog: %s" % e)
            finally:
                #self.log_debug("Restoring state of main application windows")
                # kinda important to ensure we restore other window state:
                for hwnd, state in saved_state:
                    if win32gui.IsWindowEnabled(hwnd) != state:
                        # restore the state:
                        win32gui.EnableWindow(hwnd, state)
                if foreground_window:
                    win32gui.SetForegroundWindow(foreground_window)
        else:
            # show dialog:
            status = dialog.exec_()

        return status, obj
