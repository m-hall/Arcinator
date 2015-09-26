import sublime
import sublime_plugin
import os
import os.path
import re
import subprocess
import time
from .lib import util, thread, settings, output, panels

STATUS_COMMAND = 'git status --porcelain -u all'
STATUS_UNTRACKED = r'(^|\n)\?\?'
STATUS_ADDED = r'^A[ MD]'
STATUS_STAGED = r'^M[ MD]'
STATUS_UNSTAGED = r'^[ MARC]M'
STATUS_DELETED = r'^D[ M]'
STATUS_TRACKED = r'^[^\?][^\?]'
STATUS_PARSE = r'^.. "?([^"\n]*)'

CURRENT_BRANCH_COMMAND = 'git rev-parse --abbrev-ref HEAD'


class ArcinatorCommand(sublime_plugin.WindowCommand):
    """Base command for arcinator commands"""
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
        command = [cmd] + files
        util.debug(command)
        return subprocess.Popen(command, stdout=subprocess.PIPE)

    def test_tracked(self, result):
        """Tests output to verify if a file is tracked"""
        return len(result) == 0 or re.search(STATUS_TRACKED, result, re.M) is not None

    def test_changed(self, result):
        """Tests output to verify if a file is tracked"""
        return len(result) > 0

    def is_tracked(self, files):
        """Runs a command to verify if a file is tracked"""
        status = self.run_command(STATUS_COMMAND, files, False, False)
        return self.test_tracked(status.output())

    def is_changed(self, files):
        """Runs a status command to see if a file has been changed since last revision"""
        status = self.run_command(STATUS_COMMAND, files, False, False)
        return self.test_changed(status.output())

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
        status = self.run_command(STATUS_COMMAND, files, False, False)
        tests = {
            'uid': uid,
            'file': self.is_file(files),
            'folder': self.is_folder(files),
            'single': self.is_single(files),
            'tracked': self.test_tracked(status.output()),
            'changed': self.test_changed(status.output()),
            'timestamp': time.time()
        }
        util.debug(tests)
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
        for path in matches:
            item = {
                'label': path,
                'value': path,
                'selected': self.is_tracked([path])
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
        self.run_command(STATUS_COMMAND, self.files, False, False, self.on_changes_available)

    def on_select_branch(self, index):
        """Handles completion of the MultiSelect"""
        self.branch = self.items[index]

    def parse_branches(self, raw):
        """Parses the output of a status command for use in a MultiSelect"""
        lines = raw.split('\n')
        if len(lines) < 1:
            sublime.status_message('No branches')
            return False
        items = []
        for path in lines:
            if path[:2] == '* ' or len(path) < 1:
                continue
            items.append(path.strip())
        if len(items) < 1:
            sublime.status_message('No branches')
            return False
        self.items = items
        return True

    def on_branches_available(self, process):
        """Shows the list of changes to the user"""
        output = process.output()
        if not self.parse_branches(output):
            return
        sublime.active_window().show_quick_panel(self.items, self.on_select_branch, sublime.MONOSPACE_FONT)

    def select_branch(self):
        """Gets the list of branches"""
        self.run_command('git branch', [], False, False, self.on_branches_available)

    def run(self, cmd="", paths=None, group=-1, index=-1):
        """Runs the command"""
        if cmd is "":
            return
        files = util.get_files(paths, group, index)
        self.command_name = cmd.upper()
        self.run_command(cmd, files)

    def is_enabled(self, paths=None, group=-1, index=-1):
        """Checks if the command should be visible"""
        files = util.get_files(paths, group, index)
        tests = self.test_all(files)
        for key in self.tests:
            if tests[key] != self.tests[key]:
                util.debug(self.command_name + " is disabled because a test failed (%s)" % str(key))
                return False
        return True


class ArcinatorCommitCommand(ArcinatorCommand):
    """A command that handles committing to Git"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'Commit'
        self.tests = {
            'changed': True
        }
        self.files = None
        self.message = None

    def commit(self):
        """Runs the native commit command"""
        self.run_command('git commit -m "' + util.escape_quotes(self.message) + '"', self.files)

    def verify(self):
        """Checks with the user if the commit is valid"""
        if sublime.ok_cancel_dialog(self.message + '\n\nFiles:\n' + '\n'.join(self.files)):
            self.commit()

    def on_done_input(self, value):
        """Handles completion of the input panel"""
        self.message = value
        minSize = 0
        if minSize > 0 and len(value) < minSize:
            sublime.status_message('Commit message too short')
            return
        if True:
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


class ArcinatorPushCommand(ArcinatorCommand):
    """A command that pushes to the remote"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'Push'
        self.tests = {
            'tracked': True
        }

    def run(self, paths=None, group=-1, index=-1):
        """Runs the command"""
        util.debug(self.command_name)
        self.run_command('git push', [])


class ArcinatorPullCommand(ArcinatorCommand):
    """A command that updates to HEAD"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'Pull'
        self.tests = {
            'tracked': True
        }

    def run(self, paths=None, group=-1, index=-1):
        """Runs the command"""
        util.debug(self.command_name)
        files = util.get_files(paths, group, index)
        self.run_command('git pull', files)


class ArcinatorPullRebaseCommand(ArcinatorCommand):
    """A command that rebases and updates to HEAD"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'Pull'
        self.tests = {
            'tracked': True
        }

    def run(self, paths=None, group=-1, index=-1):
        """Runs the command"""
        util.debug(self.command_name)
        files = util.get_files(paths, group, index)
        self.run_command('git pull --rebase', files)


class ArcinatorStatusCommand(ArcinatorCommand):
    """A command that gets the status of the repo"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'Status'
        self.tests = {
            # 'tracked': True
        }

    def run(self, paths=None, group=-1, index=-1):
        """Runs the command"""
        util.debug(self.command_name)
        files = util.get_files(paths, group, index)
        self.run_command('git status --porcelain -u all', files)


class ArcinatorSubmitCommand(ArcinatorCommand):
    """A command that sends a feature to arcanist for review"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'Submit for Review'
        self.tests = {
            'tracked': True
        }

    def run(self, paths=None, group=-1, index=-1):
        """Runs the command"""
        util.debug(self.command_name)
        self.run_command('arc diff --preview --browse')


class ArcinatorFeatureCommand(ArcinatorCommand):
    """A command that creates a new feature branch and switches the working copy to it"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'New Feature'
        self.tests = {
            'tracked': True
        }

    def on_done_input(self, value):
        self.run_command('arc feature ' + value)

    def run(self, paths=None, group=-1, index=-1):
        """Runs the command"""
        util.debug(self.command_name)
        p = self.run_command('git checkout trunk', [], False, False)
        if p.returncode != 0:
            sublime.message_dialog('Could not switch to trunk:\n' + p.output() + '\n' + p.error())
            return
        sublime.active_window().show_input_panel('Feature name', '', self.on_done_input, self.nothing, self.nothing)


class ArcinatorFeatureFromCurrentCommand(ArcinatorCommand):
    """A command that creates a new feature branch and switches the working copy to it"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'New Feature'
        self.tests = {
            'tracked': True
        }

    def on_done_input(self, value):
        self.run_command('arc feature ' + value)

    def run(self, paths=None, group=-1, index=-1):
        """Runs the command"""
        util.debug(self.command_name)
        sublime.active_window().show_input_panel('Feature name', '', self.on_done_input, self.nothing, self.nothing)


class ArcinatorLandCommand(ArcinatorCommand):
    """A command that lands an approved review"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'Land Review'
        self.tests = {
            'tracked': True
        }

    def run(self, paths=None, group=-1, index=-1):
        """Runs the command"""
        util.debug(self.command_name)
        self.run_command('arc land --svn-post-commit')


class ArcinatorLandOntoCommand(ArcinatorCommand):
    """A command that lands an approved review"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'Land Review Onto'
        self.tests = {
            'tracked': True
        }

    def on_select_branch(self, index):
        """Handles completion of the MultiSelect"""
        self.branch = self.items[index]
        if index < 0:
            return
        self.run_command('arc land --svn-post-commit --onto ' + self.branch)

    def run(self, paths=None, group=-1, index=-1):
        """Runs the command"""
        util.debug(self.command_name)
        self.select_branch()


class ArcinatorSwitchCommand(ArcinatorCommand):
    """A Command that will switch the current feature branch"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'Switch Branch'
        self.tests = {
            'tracked': True
        }

    def on_select_branch(self, index):
        """Handles completion of the MultiSelect"""
        self.branch = self.items[index]
        if index < 0:
            return
        self.run_command('git checkout ' + self.branch)

    def run(self, paths=None, group=-1, index=-1):
        """Runs the command"""
        util.debug(self.command_name)
        self.files = util.get_files(paths, group, index)
        self.select_branch()


class ArcinatorDiffCommand(ArcinatorCommand):
    """Run the external diff tool on the specified path"""

    def __init__(self, window):
        """Initialize the command object"""
        super().__init__(window)
        self.command_name = 'Diff'
        self.tests = {
            'tracked': True
        }

    def run(self, paths=None, group=-1, index=-1):
        """Runs the command"""
        util.debug(self.command_name)
        self.files = util.get_files(paths, group, index)
        appName = settings.get('externalDiffTool')
        self.run_external(appName, self.files)
