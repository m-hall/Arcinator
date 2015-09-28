import sublime
import sublime_plugin
from .lib import thread, menu


class ArcinatorKillProcessesCommand(sublime_plugin.WindowCommand):
    """A command that kills all of the running processes"""

    def run(self):
        """Runs the command"""
        thread.terminate_all()