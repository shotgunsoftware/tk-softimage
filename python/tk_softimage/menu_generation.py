"""

Menu handling for Softimage

"""
"""
IMPORTANT NOTE:
Softimage does not allow scripts to build or destroy menu items on the fly. Instead, menus and their functions
must be registered in advance via a Self Installing Plugin. This leads to 2 issues for compatability with Tank
(when compared to Maya or Nuke):

1) When a user clicks on the top menu (in the case, the "Tank" menu), Softimage reads the script code at that moment
and builds the submenus. In order to regenerate the menus, it is necessary for the Menu Plugin to be unloaded and 
then reloaded. For Tank, this is done each time the Tank engine is destroyed or started, such that a custom menu
set is built on a per engine basis.

2) In Maya or Nuke, when you bind a menu item to a callback, you can input the memory address of whatever the callback
function is. This makes it a non-issue to generate and update menu items on the fly via the Tank app template. In Softimage, 
it's not as direct.

The Python method Softimage uses for binding a menu callback with the menu item is Menu.AddCallbackItem2(label, callback_name)

Rather than passing the memory address of the callback into the second argument, Softimage expects the string name of the
handler function. It also assumes that function has already been defined in the memory scope of the Self Installing Plugin that
is building the menu item, which is hard to do if the menu and its associated callbacks are being generated on the fly by
Tank!

To overcome this limitation, when the MenuGenerator object is called inside the Softimage script that builds the Menus, we
pass it the globals() dictionary. For each Menu item callback, we add the name of the function to the globals() index, then bind
it to the function memory space using lambda. Then we can call Menu.AddCallbackItem2() and input the string name of the callback.
Softimage is tricked into thinking that function exists in the local memory space, and successfully registers the Menu item.

"""

import platform
import sys
import os
import unicodedata

import tank

class MenuGenerator(object):
    """
    Menu generation functionality for Softimage
    """

    # By passing the globals() dictionary from the Python Script running in Softimage, we can
    # register the callbacks for each Menu handler in the local name space for the Self Installing Plugin.
    def __init__(self, engine, menu_handle, global_dict):
        self._engine = engine
        self._menu_handle = menu_handle
        self._dialogs = []
        self.global_dict = global_dict
        
    ##########################################################################################
    # public methods

    def create_menu(self, *args):
        """
        Render the entire Tank menu.
        In order to have commands enable/disable themselves based on the enable_callback, 
        re-create the menu items every time.
        """

        # now add the context item on top of the main menu
        if self._engine.context:
            self._context_menu = self._add_context_menu()

        #Add Separator to Tank Menu
        self._menu_handle.AddSeparatorItem()

        # now enumerate all items and create menu objects for them
        menu_items = []
        for (cmd_name, cmd_details) in self._engine.commands.items():
             menu_items.append( AppCommand(cmd_name, cmd_details, self.global_dict) )

        # now add favourites
        for fav in self._engine.get_setting("menu_favourites"):
            app_instance_name = fav["app_instance"]
            menu_name = fav["name"]
            # scan through all menu items
            for cmd in menu_items:                 
                 if cmd.get_app_instance_name() == app_instance_name and cmd.name == menu_name:
                     # found our match!
                     cmd.add_command_to_menu(self._menu_handle)
                     # mark as a favourite item
                     cmd.favourite = True

        #Add Separator to Tank Menu
        self._menu_handle.AddSeparatorItem()
        
        # now go through all of the menu items.
        # separate them out into various sections
        commands_by_app = {}
        
        for cmd in menu_items:

            if cmd.get_type() == "context_menu":
                # context menu!
                cmd.add_command_to_menu(self._context_menu)             
                
            else:
                # normal menu
                app_name = cmd.get_app_name()
                if app_name is None:
                    # un-parented app
                    app_name = "Other Items" 
                if not app_name in commands_by_app:
                    commands_by_app[app_name] = []
                commands_by_app[app_name].append(cmd)
        
        # now add all apps to main menu
        self._add_app_menu(commands_by_app)

    ##########################################################################################
    # context menu and UI
        
    def _add_context_menu(self):
        """
        Adds a context menu which displays the current context
        """        
        
        ctx = self._engine.context
        
        if ctx.entity is None:
            # project-only!
            ctx_name = "%s" % ctx.project["name"]
        
        elif ctx.step is None and ctx.task is None:
            # entity only
            # e.g. [Shot ABC_123]
            ctx_name = "%s %s" % (ctx.entity["type"], ctx.entity["name"])

        else:
            # we have either step or task
            task_step = None

            if ctx.step:
                task_step = ctx.step.get("name")
            if ctx.task:
                task_step = ctx.task.get("name")
            
            # e.g. [Lighting, Shot ABC_123]
            ctx_name = "%s, %s %s" % (task_step, ctx.entity["type"], ctx.entity["name"])
        
        # create the sub menu object
        ctx_menu = self._menu_handle.AddSubMenu(ctx_name)

        ctx_menu.AddSeparatorItem()

        # To get the Softimage Self Installing Plugin to bind callbacks to the Menu Items:
        # 1) Get the name of the callback
        # 2) Point to the callback function in the globals() scope of the Self Installing script
        # 3) Run Menu.AddCallbackItem2(label, stringHandlerName) where the stringHandlerName refers to the callback from #1
        callback_name = "tank_"+getattr(self._jump_to_sg, "__name__")
        self.global_dict[callback_name] = lambda x: self._jump_to_sg(self._menu_handle)
        ctx_menu.AddCallbackItem2("Jump to Shotgun", callback_name)

        callback_name = "tank_"+getattr(self._jump_to_fs, "__name__")
        self.global_dict[callback_name] = lambda x: self._jump_to_fs()
        ctx_menu.AddCallbackItem2("Jump to File System", callback_name)

        # divider (apps may register entries below this divider)
        ctx_menu.AddSeparatorItem()
        
        return ctx_menu
                                            
    def _jump_to_sg(self, ctx):
        import webbrowser
        if self._engine.context.entity is None:
            # project-only!
            url = "%s/detail/%s/%d" % (self._engine.shotgun.base_url, 
                                       "Project", 
                                       self._engine.context.project["id"])
        else:
            # entity-based
            url = "%s/detail/%s/%d" % (self._engine.shotgun.base_url, 
                                       self._engine.context.entity["type"], 
                                       self._engine.context.entity["id"])
        webbrowser.open(url)
        
        
    def _jump_to_fs(self):
        
        """
        Jump from context to FS
        """
        
        if self._engine.context.entity:
            paths = self._engine.tank.paths_from_entity(self._engine.context.entity["type"], 
                                                     self._engine.context.entity["id"])
        else:
            paths = self._engine.tank.paths_from_entity(self._engine.context.project["type"], 
                                                     self._engine.context.project["id"])
        
        # launch one window for each location on disk
        # todo: can we do this in a more elegant way?
        for disk_location in paths:
                
            # get the setting        
            system = platform.system()
            
            # run the app
            if system == "Linux":
                cmd = 'xdg-open "%s"' % disk_location
            elif system == "Darwin":
                cmd = 'open "%s"' % disk_location
            elif system == "Windows":
                cmd = 'cmd.exe /C start "Folder" "%s"' % disk_location
            else:
                raise Exception("Platform '%s' is not supported." % system)
            
            exit_code = os.system(cmd)
            if exit_code != 0:
                self._engine.log_error("Failed to launch '%s'!" % cmd)
    
    ##########################################################################################
    # app menus
        
        
    def _add_app_menu(self, commands_by_app):
        """
        Add all apps to the main menu, process them one by one.
        """
        for app_name in sorted(commands_by_app.keys()):
            
            if len(commands_by_app[app_name]) > 1:
                # more than one menu entry fort his app
                # make a sub menu and put all items in the sub menu

                sub_menu = self._menu_handle.AddSubMenu(app_name)
                
                for cmd in commands_by_app[app_name]:
                    cmd.add_command_to_menu(sub_menu)
            
            else:

                # this app only has a single entry. 
                # display that on the menu
                # todo: Should this be labelled with the name of the app 
                # or the name of the menu item? Not sure.
                cmd_obj = commands_by_app[app_name][0]
                if not cmd_obj.favourite:
                    # skip favourites since they are alreay on the menu
                    cmd_obj.add_command_to_menu(self._menu_handle)
                                
        

class AppCommand(object):
    """
    Wraps around a single command that you get from engine.commands
    """
    
    def __init__(self, name, command_dict, global_dict):        
        self.name = name
        self.properties = command_dict["properties"]
        self.callback = command_dict["callback"]
        self.favourite = False
        self.global_dict = global_dict
        
    def get_app_name(self):
        """
        Returns the name of the app that this command belongs to
        """
        if "app" in self.properties:
            return self.properties["app"].display_name
        return None
        
    def get_app_instance_name(self):
        """
        Returns the name of the app instance, as defined in the environment.
        Returns None if not found.
        """
        if "app" not in self.properties:
            return None
        
        app_instance = self.properties["app"]
        engine = app_instance.engine

        for (app_instance_name, app_instance_obj) in engine.apps.items():
            if app_instance_obj == app_instance:
                # found our app!
                return app_instance_name
            
        return None
        
    def get_documentation_url_str(self):
        """
        Returns the documentation as a str
        """
        if "app" in self.properties:
            app = self.properties["app"]
            doc_url = app.documentation_url
            # deal with nuke's inability to handle unicode. #fail
            if doc_url.__class__ == unicode:
                doc_url = unicodedata.normalize('NFKD', doc_url).encode('ascii', 'ignore')
            return doc_url

        return None
        
    def get_type(self):
        """
        returns the command type. Returns node, custom_pane or default
        """
        return self.properties.get("type", "default")
        
    def add_command_to_menu(self, menu):
        """
        Adds an app command to the menu
        """
        enabled = True
        
        if "enable_callback" in self.properties:
            enabled = self.properties["enable_callback"]()
        
        # To get the Softimage Self Installing Plugin to bind callbacks to the Menu Items:
        # 1) Get the name of the callback
        # 2) Point to the callback function in the globals() scope of the Self Installing script
        # 3) Run Menu.AddCallbackItem2(label, stringHandlerName) where the stringHandlerName refers to the callback from #1

        callback_name = self.get_app_instance_name() + "_" + getattr(self.callback, "__name__")
        if self.global_dict.get(callback_name):
            raise Exception("Could not register menu callback due to conflicting namespace: %s" % callback_name)
        else:            
            self.global_dict[callback_name] = lambda x: self.callback()
        
            menu.AddCallbackItem2(self.name, callback_name)