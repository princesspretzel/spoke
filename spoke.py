import encodings
import json
import os
import re
import sublime
import sublime_plugin
import subprocess
import threading
import urllib
import urllib2

class Spoke(sublime_plugin.TextCommand):
    def run(self, edit):
        if self.run_command(['git', 'rev-parse', '--is-inside-work-tree']).strip() == 'true':
            self.remote = 'root'
            remote_url = self.run_command(['git', 'config', '--get', 'remote.'+self.remote+'.url']).strip()
            if not remote_url:
                self.remote = 'origin'
                remote_url = self.run_command(['git', 'config', '--get', 'remote.'+self.remote+'.url']).strip()
            print remote_url
            match = re.search('(\w*)[/:]([\w-]*).git\Z', remote_url)
            self.username = match.group(1)
            self.repo = match.group(2)
            self.view.window().show_input_panel("Github Pull Request:", '', self.on_done, None, None)
        else:
            sublime.error_message('Not in a git directory')
    
    def on_done(self, pull_request_id):
        github = GitHubApi(self.username, self.repo)
        self.run_command(['git', 'fetch', self.remote, 'pull/'+pull_request_id+'/head:'+self.remote+'/pull/'+pull_request_id+'/head'])
        self.run_command(['git', 'checkout', self.remote+'/pull/'+pull_request_id+'/head'])
        files = github.get_pull_request(pull_request_id)
        for f in files:
            sublime.active_window().open_file(sublime.active_window().folders()[0] + "/" + f)
        print(files)


    def run_command(self, args):
        startupinfo = None
        print sublime.active_window().folders()[0]
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                                startupinfo=startupinfo, stderr=subprocess.PIPE, cwd=sublime.active_window().folders()[0])
        output = proc.stdout.read()
        print output
        return output

'''
Uses GitHub API to grab pull requests
Extends threading to run API calls in the background & prevent lag
'''
class GitHubApi(threading.Thread):
    def __init__(self, username, repo, base_uri="https://api.github.com/repos/", token=None):
        self.base_uri = base_uri
        self.token = token
        self.username = username
        self.repo = repo
        threading.Thread.__init__(self)

    def get_pull_request(self, pull_request):
        files = []
        url = self.base_uri + self.username + "/" + self.repo + "/pulls/" + pull_request + "/files?access_token=d5add3a1f915b745a73622e3f6b7b1fc4b7e1bce"
        print url
        data = json.load(urllib2.urlopen(url))
        for f in data:
            files.append(f['filename'])
        return files

thread = GitHubApi(target=get_pull_request, args=(pull_request))
thread.start()
