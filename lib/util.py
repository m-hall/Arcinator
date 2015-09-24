import sublime
import os
import re
from . import settings

URL_TEST = r"(http|https|git)?:\/\/.*"


def get_files(paths=None, group=-1, index=-1, base=None):
    """Get a list of files based on command input"""
    if base is None:
        base = settings.get('commandBaseFiles', 'project')
    files = []
    if isinstance(paths, list):
        files = files+paths
    if group >= 0 and index >= 0:
        view = sublime.active_window().views_in_group(group)[index]
        files.append(view.file_name())
    if len(files) == 0:
        if base == 'current':
            view = sublime.active_window().active_view()
            file_name = view.file_name()
            if file_name is not None and os.path.exists(file_name):
                files.append(file_name)
        elif base == 'project':
            folders = sublime.active_window().folders()
            return folders
        elif isinstance(base, list):
            for b in base:
                b = os.path.expanduser(b)
                if os.path.exists(b):
                    files.append(b)
        elif os.path.exists(os.path.expanduser(base)):
            files.append(os.path.expanduser(base))
    return files


def debug(message):
    """Send output to console if debugging is enabled"""
    if settings.get("debug", False):
        print('Arcinator: ' + str(message))


def is_url(url):
    return re.match(URL_TEST, url) is not None


def escape_quotes(message):
    """Escapes quotes in a message."""
    return message.replace('"', '\\"')
