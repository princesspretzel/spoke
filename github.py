import urllib, urllib2, threading

'''
Makes sure API calls are happening in the background to prevent lag
Uses GitHub API to grab pull requests
'''
class GitHubApi(threading.Thread):
    def __init__(self, base_uri="https://api.github.com/repos/", token=None, pull_request, string, timeout):
        self.pull_request = pull_request
        self.original = string
        self.timeout = timeout
        self.result = None
        threading.Thread.__init__(self)

    def run(self, pull_request):
        url = pull_request
        try:
            data = 
            result = urllib2.urlopen(url)
            run(result)
        except (urllib2.HTTPError) as (e):
            err = '%s: HTTP error %s contacting API' % (__name__, str(e.code))
        except (urllib2.URLError) as (e):
            err = '%s: URL error %s contacting API' % (__name__, str(e.reason))

    def get(self, endpoint, params=None):
        return self.request('get', endpoint, params=params)

    def get_pull_request(self, pull_request):
        data = self.get(base_uri + username + "/pulls" + pull_request + "/files")
        return list(data["files"].values())[0]["content"]
