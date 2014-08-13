import encodings
import json
import os
import os.path
import re
import sublime
import sublime_plugin
import subprocess
import sys
import threading
import urllib
import urllib2
import sys
import os.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sublime
import json
import sublime_requests as requests
import logging
from requests.exceptions import ConnectionError
import pprint

logging.basicConfig(format='%(asctime)s %(message)s')
logger = logging.getLogger()


class GitHubApi(object):
    "Encapsulates the GitHub API"
    PER_PAGE = 100
    etags = {}
    cache = {}

    class UnauthorizedException(Exception):
        "Raised if we get a 401 from GitHub"
        pass

    class OTPNeededException(Exception):
        "Raised if 2FA is configured and we need a one-time password"
        pass

    class UnknownException(Exception):
        "Raised if we get a response code we don't recognize from GitHub"
        pass

    class ConnectionException(Exception):
        "Raised if we get a ConnectionError"
        pass

    class NullResponseException(Exception):
        "Raised if we get an empty response (i.e., CurlSession failure)"
        pass

    def __init__(self, base_uri="https://api.github.com", token=None, debug=False, proxies=None, force_curl=False):
        self.base_uri = base_uri
        self.token = token
        self.debug = debug
        self.proxies = proxies

        if debug:
            try:
                import http.client as httplib
            except ImportError:
                import httplib
            httplib.HTTPConnection.debuglevel = 1
            logger.setLevel(logging.DEBUG)
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True

        # set up requests session with the root CA cert bundle
        cert_path = os.path.join(sublime.packages_path(), "sublime-github", "ca-bundle.crt")
        if not os.path.isfile(cert_path):
            logger.warning("Root CA cert bundle not found at %s! Not verifying requests." % cert_path)
            cert_path = None
        self.rsession = requests.session(verify=cert_path,
                                         force_curl=force_curl)

    def get_token(self, username, password, one_time_password=None):
        auth_data = {
            "scopes": ["repo"],
            "note": "Sublime GitHubaaa",
            "note_url": "https://github.com/bgreenlee/sublime-github"
        }
        headers = {'X-GitHub-OTP': one_time_password} if one_time_password else {}
        resp = self.rsession.post(self.base_uri + "/authorizations",
                                  headers=headers,
                                  auth=(username, password),
                                  proxies=self.proxies,
                                  data=json.dumps(auth_data))
        if resp.status_code == requests.codes.CREATED:
            logger.debug(pprint.saferepr(resp))
            data = json.loads(resp.text)
            return data["token"]
        elif resp.status_code == requests.codes.UNAUTHORIZED:
            if resp.headers['X-GitHub-OTP'].startswith('required'):
                raise self.OTPNeededException()
            else:
                raise self.UnauthorizedException()
        else:
            raise self.UnknownException("%d %s" % (resp.status_code, resp.text))

    def post(self, endpoint, data=None, content_type='application/json'):
        return self.request('post', endpoint, data=data, content_type=content_type)

    def patch(self, endpoint, data=None, content_type='application/json'):
        return self.request('patch', endpoint, data=data, content_type=content_type)

    def get(self, endpoint, params=None):
        return self.request('get', endpoint, params=params)

    def request(self, method, url, params=None, data=None, content_type=None):
        if not url.startswith("http"):
            url = self.base_uri + url
        if data:
            data = json.dumps(data)

        headers = {"Authorization": "token %s" % self.token}

        if content_type:
            headers["Content-Type"] = content_type

        # add an etag to the header if we have one
        if method == 'get' and url in self.etags:
            headers["If-None-Match"] = self.etags[url]
        logger.debug("request: %s %s %s %s" % (method, url, headers, params))

        try:
            resp = self.rsession.request(method, url,
                                     headers=headers,
                                     params=params,
                                     data=data,
                                     proxies=self.proxies,
                                     allow_redirects=True)
            if not resp:
                raise self.NullResponseException("Empty response received.")
        except ConnectionError as e:
            raise self.ConnectionException("Connection error, "
                "please verify your internet connection: %s" % e)

        full_url = resp.url
        logger.debug("response: %s" % resp.headers)
        if resp.status_code in [requests.codes.OK,
                                requests.codes.CREATED,
                                requests.codes.FOUND,
                                requests.codes.CONTINUE]:
            if 'application/json' in resp.headers['Content-Type']:
                resp_data = json.loads(resp.text)
            else:
                resp_data = resp.text
            if method == 'get':  # cache the response
                etag = resp.headers['ETag']
                self.etags[full_url] = etag
                self.cache[etag] = resp_data
            return resp_data
        elif resp.status_code == requests.codes.NOT_MODIFIED:
            return self.cache[resp.headers['ETag']]
        elif resp.status_code == requests.codes.UNAUTHORIZED:
            raise self.UnauthorizedException()
        else:
            raise self.UnknownException("%d %s" % (resp.status_code, resp.text))

    def create_gist(self, description="", filename="", content="", public=False):
        return self.post("/gists", {"description": description,
                                    "public": public,
                                    "files": {filename: {"content": content}}})

    def get_gist(self, gist):
        data = self.get("/gists/" + gist["id"])
        return list(data["files"].values())[0]["content"]

    def update_gist(self, gist, content):
        filename = list(gist["files"].keys())[0]
        return self.patch("/gists/" + gist["id"],
                         {"description": gist["description"],
                          "files": {filename: {"content": content}}})

    def list_gists(self, starred=False):
        page = 1
        data = []
        # fetch all pages
        while True:
            endpoint = "/gists" + ("/starred" if starred else "")
            page_data = self.get(endpoint, params={'page': page, 'per_page': self.PER_PAGE})
            data.extend(page_data)
            if len(page_data) < self.PER_PAGE:
                break
            page += 1
        return data


class BaseGitHubCommand(sublime_plugin.WindowCommand):
    """
    Base class for all GitHub commands. Handles getting an auth token.
    """
    MSG_USERNAME = "GitHub username:"
    MSG_PASSWORD = "GitHub password:"
    MSG_ONE_TIME_PASSWORD = "One-time passowrd (for 2FA):"
    MSG_TOKEN_SUCCESS = "Your access token has been saved. We'll now resume your command."
    ERR_NO_USER_TOKEN = "Your GitHub Gist access token needs to be configured.\n\n"\
        "Click OK and then enter your GitHub username and password below (neither will "\
        "be stored; they are only used to generate an access token)."
    ERR_UNAUTHORIZED = "Your Github username or password appears to be incorrect. "\
        "Please try again."
    ERR_UNAUTHORIZED_TOKEN = "Your Github token appears to be incorrect. Please re-enter your "\
        "username and password to generate a new token."

    def run(self):
        self.settings = sublime.load_settings("GitHub.sublime-settings")
        self.github_user = None
        self.github_password = None
        self.github_one_time_password = None
        self.accounts = self.settings.get("accounts")
        self.active_account = self.settings.get("active_account")
        if not self.active_account:
            self.active_account = list(self.accounts.keys())[0]
        self.github_token = self.accounts[self.active_account]["github_token"]
        if not self.github_token:
            self.github_token = self.settings.get("github_token")
            if self.github_token:
                # migrate to new structure
                self.settings.set("accounts", {"GitHub": {"base_uri": "https://api.github.com", "github_token": self.github_token}})
                self.settings.set("active_account", "GitHub")
                self.active_account = self.settings.get("active_account")
                self.settings.erase("github_token")
                sublime.save_settings("GitHub.sublime-settings")
        self.base_uri = self.accounts[self.active_account]["base_uri"]
        self.debug = self.settings.get('debug')

        self.proxies = {'https': self.accounts[self.active_account].get("https_proxy", None)}
        self.force_curl = False
        self.gistapi = GitHubApi(self.base_uri, self.github_token, debug=self.debug,
                                 proxies=self.proxies, force_curl=self.force_curl)

    def get_token(self):
        sublime.error_message(self.ERR_NO_USER_TOKEN)
        self.get_username()

    def get_username(self):
        self.window.show_input_panel(self.MSG_USERNAME, self.github_user or "", self.on_done_username, None, None)

    def get_password(self):
        self.window.show_input_panel(self.MSG_PASSWORD, "", self.on_done_password, None, None)

    def get_one_time_password(self):
        self.window.show_input_panel(self.MSG_ONE_TIME_PASSWORD, "", self.on_done_one_time_password, None, None)

    def on_done_username(self, value):
        "Callback for the username show_input_panel."
        self.github_user = value
        # need to do this or the input panel doesn't show
        sublime.set_timeout(self.get_password, 50)

    def on_done_one_time_password(self, value):
        "Callback for the one-time password show_input_panel"
        self.github_one_time_password = value
        self.on_done_password(self.github_password)

    def on_done_password(self, value):
        "Callback for the password show_input_panel"
        self.github_password = value
        try:
            api = GitHubApi(self.base_uri, debug=self.debug)
            self.github_token = api.get_token(self.github_user,
                                              self.github_password,
                                              self.github_one_time_password)
            self.github_password = self.github_one_time_password = None  # don't keep these around
            self.accounts[self.active_account]["github_token"] = self.github_token
            self.settings.set("accounts", self.accounts)
            sublime.save_settings("GitHub.sublime-settings")
            self.gistapi = GitHubApi(self.base_uri, self.github_token, debug=self.debug)
            try:
                if self.callback:
                    sublime.error_message(self.MSG_TOKEN_SUCCESS)
                    callback = self.callback
                    self.callback = None
                    sublime.set_timeout(callback, 50)
            except AttributeError:
                pass
        except GitHubApi.OTPNeededException:
            sublime.set_timeout(self.get_one_time_password, 50)
        except GitHubApi.UnauthorizedException:
            sublime.error_message(self.ERR_UNAUTHORIZED)
            sublime.set_timeout(self.get_username, 50)
        except GitHubApi.UnknownException as e:
            sublime.error_message(e.message)

class Spoke(BaseGitHubCommand):
    def run(self):
        super(Spoke, self).run()
        if self.github_token:
            self.spoke()
        else:
            self.callback = self.spoke
            self.get_token()

    def spoke(self):
        self.window.show_input_panel("Github Pull Request:", '', self.on_done, None, None)

    def on_done(self, pull_request_id):
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
            github = GitHubApi2(self.github_token, self.username, self.repo, self)
            self.run_command(['git', 'fetch', self.remote, 'pull/'+pull_request_id+'/head:'+self.remote+'/pull/'+pull_request_id+'/head'])
            self.run_command(['git', 'checkout', self.remote+'/pull/'+pull_request_id+'/head'])
            files = github.get_pull_request(pull_request_id)
            for f in files:
                sublime.active_window().open_file(sublime.active_window().folders()[0] + "/" + f)
            print(files)
        else:
            sublime.error_message('Not in a git directory')

    def run_command(self, args):
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                                startupinfo=startupinfo, stderr=subprocess.PIPE, cwd=sublime.active_window().folders()[0])
        output = proc.stdout.read()
        return output

'''
Uses GitHub API to grab pull requests
Extends threading to run API calls in the background & prevent lag
'''

class GitHubApi2():
    def __init__(self, github_token, username, repo, spoke, base_uri="https://api.github.com/repos/", token=None):
        self.base_uri = base_uri
        self.username = username
        self.repo = repo
        self.token = github_token

    def get_pull_request(self, pull_request_id):
        files = []
        url = self.base_uri + self.username + "/" + self.repo + "/pulls/" + pull_request_id + "/files?access_token=" + self.token
        print url
        data = json.load(urllib2.urlopen(url))
        for f in data:
            files.append(f['filename'])
        for f in files:
            sublime.set_timeout(lambda f=f: sublime.active_window().open_file(sublime.active_window().folders()[0] + "/" + f), 0)

    def run(self):
        self.get_pull_request()
