import json, urllib, urllib2, threading

'''
Makes sure API calls are happening in the background to prevent lag
Uses GitHub API to grab pull requests
'''
class GitHubApi(threading.Thread):
    def __init__(self, base_uri="https://api.github.com/repos/", token=None, timeout, username):
        self.base_uri = base_uri
        self.token = token
        self.timeout = timeout
        self.username = username
        threading.Thread.__init__(self)

    def get(self, endpoint, params=None):
        return self.request('get', endpoint, params=params)

    def get_pull_request(self, pull_request):
        try:
            data = json.load(urllib2.urlopen(base_uri + username + "/pulls" + pull_request + "/files"))
            return data["filename"]
