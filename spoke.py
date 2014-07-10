import encodings
import re
import sublime
import sublime_plugin
import subprocess

'''
Main command-line functionality
''' 
class Spoke(sublime_plugin.TextCommand):
    def run(self, edit):
        self.run_command(['git', 'fetch', 'root', 'pull/{pull_request}/head:root/pull{pull_request}/head'])
        self.run_command(['git', 'checkout', 'root/pull/{pull_request}/head'])

    def run_command(self, args):
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                                startupinfo=startupinfo, stderr=subprocess.PIPE, cwd=sublime.active_window().folders()[0])
        results = proc.stdout.read()
        print(results)
        return results
