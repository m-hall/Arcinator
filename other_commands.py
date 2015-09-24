import sublime
import sublime_plugin
from .lib import thread, menu


class ArcinatorKillProcessesCommand(sublime_plugin.WindowCommand):
    """A command that kills all of the running processes"""

    def run(self):
        """Runs the command"""
        thread.terminate_all()


class ArcinatorResetSideBarCommand(sublime_plugin.WindowCommand):
    """A command that resets the side bar to the default"""

    def run(self):
        """Runs the command"""
        menu.remove_user_side_bar()
        menu.create_user_side_bar()
