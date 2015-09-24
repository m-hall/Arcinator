import sublime_plugin
from .lib import output


class OutputViewEvents(sublime_plugin.EventListener):
    """Handles events for the SVN View"""

    def on_close(self, view):
        """Stop using the view if it has been closed"""
        output.OutputView.close(view)