"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Implements the Softimage Engine in Tank.
"""

import sys, os

import tank
from tank.platform import Engine

import win32com
from win32com.client import Dispatch, constants

Application = Dispatch("XSI.Application").Application
XSIFactory = Dispatch("XSI.Factory")
XSIUtils = Dispatch("XSI.Utils")
XSIToolkit = Dispatch("XSI.UIToolkit")


class TankProgressWrapper(object):
    """
    A progressbar wrapper.
    """
    def __init__(self, title):
        self.__title = title
        self._progress_bar = XSIToolkit.ProgressBar
        self._progress_bar.Caption = self.__title
        self._progress_bar.Maximum = 100

    def show(self):
        self._progress_bar.Visible = 1

    def close(self):
        self._progress_bar.Visible = 0

    def set_progress(self, percent):
        self._progress_bar.Value = percent
        print("TANK_PROGRESS Task:%s Progress:%d%%" % (self.__title, percent))


class SoftimageEngine(Engine):

    ##########################################################################################
    # init and destroy

    def init_engine(self):
        self._menu_generator = None

        # keep handles to all qt dialogs to help GC
        self.__created_qt_dialogs = []

        # create queue
        self._queue = []

        # Set the Softimage project based on config
        self._set_project()

        # add qt paths and dlls
        if self.has_ui:
            self._init_pyside()

    def post_app_init(self):
        """
        Called when all apps have initialized
        """
        if self.has_ui:
            self._create_menu()
    
    def destroy_engine(self):
        self.log_debug("%s: Destroying..." % self)
        
        # clean up UI:
        if self.has_ui:
            self._destroy_menu()

    def _init_pyside(self):
        self.log_debug("Initializing PySide integration")

        # (Re-)load Qt integration plugins
        if sys.platform == "win32":
            plugins_path = os.path.join(os.path.dirname(__file__),
                                        "resources", "rdoQtForSoftimage",
                                        "Application", "Plugins")
            
            Application.UnloadPlugin(os.path.join(plugins_path, "qtevents.py"))
            Application.UnloadPlugin(os.path.join(plugins_path, "rdoQtForSoftimage.py"))

            Application.LoadPlugin(os.path.join(plugins_path, "rdoQtForSoftimage.py"))
            Application.LoadPlugin(os.path.join(plugins_path, "qtevents.py"))
        else:
            self.log_error("PySide integration not supported on platform: %s" % sys.platform)
            return

        # Very important -- without this call, trying to use PySide may cause Softimage to crash hard.
        # This initializes the QApplication and main event loop.
        from Qt import getQtSoftimageAnchor
        getQtSoftimageAnchor()

    def _create_menu(self):
        tk_softimage = self.import_module("tk_softimage")
        self._menu_generator = tk_softimage.MenuGenerator(self)

        # Register the menu generator somewhere where the menu plugin can find it.
        #
        # Can't use current_engine() because that's not updated by the time
        # post_app_init() is called.
        tank.platform.__si_menu_generator__ = self._menu_generator

        # Reload the menu plugin
        menu_plugin_path = os.path.join(os.path.dirname(__file__),
                                        "resources", "Tank", "Application",
                                        "Plugins", "TankMenu.py")
        Application.UnloadPlugin(menu_plugin_path)
        Application.LoadPlugin(menu_plugin_path)

    def _destroy_menu(self):
        # Unload the menu plugin
        menu_plugin_path = os.path.join(os.path.dirname(__file__),
                                        "resources", "Tank", "Application",
                                        "Plugins", "TankMenu.py")
        Application.UnloadPlugin(menu_plugin_path)

        # Unregister the menu generator
        del tank.platform.__si_menu_generator__

    ##########################################################################################
    # logging

    def log_debug(self, msg):
        if self.get_setting("debug_logging", False):
            Application.LogMessage(msg, constants.siInfo)

    def log_info(self, msg):
        Application.LogMessage(msg, constants.siInfo)

    def log_warning(self, msg):
        Application.LogMessage(msg, constants.siWarning)

    def log_error(self, msg):
        import traceback
        tb = traceback.print_exc()
        if tb:
            msg = tb+"\n"+msg
        Application.LogMessage(msg, constants.siError)

    ##########################################################################################
    # scene and project management

    def _set_project(self):
        """
        Set the softimage project
        """
        setting = self.get_setting("template_project")
        if setting is None:
            return

        tmpl = self.tank.templates.get(setting)
        fields = self.context.as_template_fields(tmpl)
        proj_path = tmpl.apply_fields(fields)
        self.log_info("Setting Softimage project to '%s'" % proj_path)

        try:
            # Disable the preference that might prompt user about project creation
            Application.Preferences.SetPreferenceValue("data_management.projects_new_project", 2)

            # Set the current project in Softimage
            Application.ActiveProject = proj_path
        except:
            self.log_error("Error setting Softimage Project: %s" % proj_path)

    ##########################################################################################
    # queue

    def add_to_queue(self, name, method, args):
        """
        Terminal implementation of the engine synchronous queue. Adds an item to the queue.
        """
        qi = {}
        qi["name"] = name
        qi["method"] = method
        qi["args"] = args
        self._queue.append(qi)

    def report_progress(self, percent):
        """
        Callback function part of the engine queue. This is being passed into the methods
        that are executing in the queue so that they can report progress back if they like
        """
        self._current_queue_item["progress_obj"].set_progress(percent)

    def execute_queue(self):
        """
        Executes all items in the queue, one by one, in a controlled fashion
        """
        # create progress items for all queue items
        for x in self._queue:
            x["progress_obj"] = TankProgressWrapper(x["name"])

        # execute one after the other syncronously
        while len(self._queue) > 0:

            # take one item off
            self._current_queue_item = self._queue.pop(0)

            # process it
            try:
                kwargs = self._current_queue_item["args"]
                # force add a progress_callback arg - this is by convention
                kwargs["progress_callback"] = self.report_progress
                # execute
                self._current_queue_item["method"](**kwargs)
            except:
                # error and continue
                # todo: may want to abort here - or clear the queue? not sure.
                self.log_error("Error while processing callback %s" % self._current_queue_item)
            finally:
                self._current_queue_item["progress"].close()

    ########################################################################################
    # QT Implementation
    
    def show_dialog(self, title, bundle, widget_class, *args, **kwargs):
        """
        Shows a non-modal dialog window in a way suitable for this engine. 
        The engine will attempt to parent the dialog nicely to the host application.
        
        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget_class: The class of the UI to be constructed. This must derive from QWidget.
        
        Additional parameters specified will be passed through to the widget_class constructor.
        
        :returns: the created widget_class instance
        """
        if not self.has_ui:
            self.log_error("Sorry, this environment does not support UI display! Cannot show "
                           "the requested window '%s'." % title)
            return
        
        from tank.platform.qt import tankqdialog
        from PySide import QtCore, QtGui
        
        # first construct the widget object
        obj = widget_class(*args, **kwargs)
        
        # now create a dialog to put it inside
        parent = self._get_parent_widget()
        dialog = tankqdialog.TankQDialog(title, bundle, obj, parent)
        
        # keep a reference to all created dialogs to make GC happy
        self.__created_qt_dialogs.append(dialog)
        
        # finally show it
        dialog.show()
        
        # lastly, return the instantiated class
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
        if not self.has_ui:
            self.log_error("Sorry, this environment does not support UI display! Cannot show "
                           "the requested window '%s'." % title)
            return
        
        from tank.platform.qt import tankqdialog 
        from PySide import QtCore, QtGui
        
        # first construct the widget object
        obj = widget_class(*args, **kwargs)
        
        # now create a dialog to put it inside
        parent = self._get_parent_widget()
        dialog = tankqdialog.TankQDialog(title, bundle, obj, parent)
        
        # keep a reference to all created dialogs to make GC happy
        self.__created_qt_dialogs.append(dialog)
        
        # finally launch it, modal state
        status = dialog.exec_()
        
        # lastly, return the instantiated class
        return (status, obj)

    @property
    def has_ui(self):
        """
        Detect and return if nuke is running in batch mode
        """
        return Application.Interactive

    def _get_parent_widget(self):
        from Qt import getQtSoftimageAnchor
        return getQtSoftimageAnchor()
