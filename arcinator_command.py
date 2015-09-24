import sublime
import sublime_plugin
import os
import os.path
import re
import subprocess
import time
from .lib import util, thread, settings, output, panels

LOG_PARSE = r'-{72}[\r\n]+r(\d+) \| ([^|]+) \| ([^|]+) \| [^\n\r]+[\n\r]+(.+)'
STATUS_PARSE = r'(^[A-W\?\!\ >]+?) +(\+ +)?(.*)'
INFO_PARSE_REVISION = r'Revision: (\d+)'
INFO_PARSE_LAST_CHANGE = r'Last Changed Rev: (\d+)'
INFO_PARSE_URL = r'URL: ([^\n]*)'


class ArcinatorCommand(sublime_plugin.WindowCommand):
    """Base command for svn commands"""
    recent_files = []

    def __init__(self, window):
        """Initializes the ArcinatorCommand object"""
        super().__init__(window)
        self.command_name = 'Arcinator Command'
        self.tests = {}

    def nothing(self, nothing1=None, nothing2=None, nothing3=None, **args):
        """Does nothing, just a placeholder for things I don't handle"""
        return

    def run_command(self, cmd, files=None, log=True, async=True, on_complete=None):
        """Starts a process for a native command"""
        return thread.Process(self.command_name, cmd, files, log, async, on_complete)

    def run_external(self, cmd, files):
        """Starts a process for an external command that should run without """
        if not util.use_tortoise():
            sublime.error_message('Tortoise command can not be run: ' + cmd)
            return
        command = cmd + ' ' + ' '.join(files)
        util.debug(command)
        return subprocess.Popen(command, stdout=subprocess.PIPE)

    def test_versionned(self, result):
        """Tests output to verify if a file is versionned"""
        return re.search(INFO_PARSE_REVISION, result, re.M) is not None

    def is_versionned(self, files):
        """Runs a command to verify if a file is versionned"""
        if len(files) == 0:
            return False

        for f in files:
            p = self.run_command('info', [f], False, False)
            if self.test_versionned(p.output() + p.error()) is True:
                return True
        return False

    def is_changed(self, files):
        """Runs a status command to see if a file has been changed since last revision"""
        p = self.run_command('status', files, False, False)
        return bool(p.output())

    def is_unchanged(self, files):
        """Checks if a file is unchanged since last revision"""
        return not self.is_changed(files)

    def is_single(self, files):
        """Checks if the list of files contains only 1 file"""
        if len(files) == 1:
            return True
        return False

    def is_file(self, files):
        """Checks if a file is actually a file"""
        if self.is_single(files) and os.path.isfile(files[0]):
            return True
        return False

    def is_folder(self, files):
        """Checks if a file is actually a folder"""
        if self.is_single(files) and not os.path.isfile(files[0]):
            return True
        return False

    def test_all(self, files):
        """Gets the result of all of the tests"""
        uid = "*".join(files)
        for tests in ArcinatorCommand.recent_files:
            if time.time() - tests['timestamp'] > 1:
                ArcinatorCommand.recent_files.remove(tests)
                continue
            if uid == tests['uid']:
                return tests
        tests = {
            'uid': uid,
            'file': self.is_file(files),
            'folder': self.is_folder(files),
            'single': self.is_single(files)
        }
        tests['versionned'] = self.is_versionned(files)
        tests['changed'] = self.is_changed(files)
        tests['timestamp'] = time.time()
        ArcinatorCommand.recent_files.append(tests)
        return tests

    def on_complete_select(self, values):
        """Handles completion of the MultiSelect"""
        self.files = values

    def parse_changes(self, raw):
        """Parses the output of a status command for use in a MultiSelect"""
        matches = re.findall(STATUS_PARSE, raw, re.M)
        if len(matches) < 1:
            sublime.status_message('No changes')
            return False
        items = []
        for change, modifier, path in matches:
            inSVN = self.is_versionned([path])
            item = {
                'label': path,
                'value': path,
                'selected': inSVN
            }
            items.append(item)
        self.items = items
        return True

    def on_changes_available(self, process):
        """Shows the list of changes to the user"""
        output = process.output()
        if not self.parse_changes(output):
            return
        panels.MultiSelect(self.items, self.on_complete_select, show_select_all=True)

    def select_changes(self):
        """Gets the committable changes"""
        thread.Process('Log', 'svn status', self.files, False, True, self.on_changes_available)

    def get_url(self, file):
        """Gets the url for a file"""
        p = self.run_command('info', [file], False, False)
        m = re.search(INFO_PARSE_URL, p.output(), re.M)
        return m.group(1)

    def run(self, cmd="", paths=None, group=-1, index=-1):
        """Runs the command"""
        if cmd is "":
            return
        files = util.get_files(paths, group, index)
        self.command_name = cmd.upper()
        self.run_command(cmd, files)

    def is_visible(self, paths=None, group=-1, index=-1):
        """Checks if the command should be visible"""
        files = util.get_files(paths, group, index)
        tests = self.test_all(files)
        for key in self.tests:
            if tests[key] != self.tests[key]:
                util.debug(self.command_name + " is not visible because a test failed (%s)" % str(key))
                return False
        return True


class ArcinatorCommitCommand(ArcinatorCommand):
    """A command that handles committing to SVN"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'Commit'
        self.tests = {
            'versionned': True
        }
        self.files = None
        self.message = None

    def commit(self):
        """Runs the native commit command"""
        self.run_command('commit -m "' + util.escape_quotes(self.message) + '"', self.files)

    def verify(self):
        """Checks with the user if the commit is valid"""
        if sublime.ok_cancel_dialog(self.message + '\n\nFiles:\n' + '\n'.join(self.files)):
            self.commit()

    def on_done_input(self, value):
        """Handles completion of the input panel"""
        self.message = value
        minSize = settings.get_native('commitMessageSize', 0)
        if minSize > 0 and len(value) < minSize:
            sublime.status_message('Commit message too short')
            return
        if settings.get_native('commitConfirm', True):
            self.verify()
        else:
            self.commit()

    def show_message_panel(self):
        """Opens an input panel to get the commit message"""
        sublime.active_window().show_input_panel('Commit message', '', self.on_done_input, self.nothing, self.nothing)

    def on_complete_select(self, values):
        """Handles completion of the MultiSelect"""
        self.files = values
        self.show_message_panel()

    def run(self, paths=None, group=-1, index=-1):
        """Runs the command"""
        util.debug(self.command_name)
        files = util.get_files(paths, group, index)
        self.files = files
        if self.is_file(files):
            self.show_message_panel()
        else:
            self.select_changes()


class ArcinatorPullCommand(ArcinatorCommand):
    """A command that updates to HEAD"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'Update'
        self.tests = {
            # 'versionned': True
        }

    def run(self, paths=None, group=-1, index=-1):
        """Runs the command"""
        util.debug(self.command_name)
        files = util.get_files(paths, group, index)
        self.run_command('update', files)