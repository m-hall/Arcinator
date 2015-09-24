import sublime
import sublime_plugin
import os
import json

SETTINGS_FILE = "Arcinator.sublime-settings"
GLOBAL_PREFERENCES = "Preferences.sublime-settings"
LISTENER_PREFIX = 'Arcinator-'


class Settings:
    """Interface for communicating with settings"""
    plugin = None

    def load():
        """Loads the settings for the plugin"""
        Settings.plugin = sublime.load_settings(SETTINGS_FILE)

    def get(name, default=None):
        """Gets a value from the plugin settings"""
        if not Settings.plugin:
            Settings.load()

        plugin = Settings.plugin
        project = sublime.active_window().project_data() or {}
        project = project.get('Arcinator', {})
        project_value = project.get(name, None)
        if project_value is not None:
            return project_value
        return plugin.get(name, default)


def get(name, default=None):
    """Gets a value from settings"""
    return Settings.get(name, default)

