import subprocess
import encodings
import re
import sublime, sublime_plugin, os
import github

import json
import urllib
import urllib2

class Spoke(sublime_plugin.TextCommand):
    def run(self, edit):
        # sublime
        # sublime.active_window().open_file('/Users/ivantse/Sites/paperlesspost/paperless-post/app/controllers/photo_albums_controller.rb')
        
        self.view.window().show_input_panel("Github Pull Request:", '', self.on_done, None, None)
    
    def on_done(self, pull_request_id):
        github = GitHubApi('paperlesspost')
        self.run_command(['git', 'fetch', 'root', 'pull/'+pull_request_id+'/head:root/pull/'+pull_request_id+'/head'])
        self.run_command(['git', 'checkout', 'root/pull/'+pull_request_id+'/head'])
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
        return output

'''
Uses GitHub API to grab pull requests
'''
class GitHubApi():
    def __init__(self, username, base_uri="https://api.github.com/repos/", token=None):
        self.base_uri = base_uri
        self.token = token
        self.username = username

    def get_pull_request(self, pull_request):
        files = []
        # print(self.base_uri + self.username + "/paperless-post" + "/pulls/" + pull_request + "/files?access_token=69ebc1c048e4858175bfd65835eebbcb78102705")
        data = json.load(urllib2.urlopen(self.base_uri + self.username + "/paperless-post" + "/pulls/" + pull_request + "/files?access_token=69ebc1c048e4858175bfd65835eebbcb78102705"))
        for f in data:
            files.append(f['filename'])
        return files
