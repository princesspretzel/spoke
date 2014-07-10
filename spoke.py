import sublime, sublime_plugin

'''
Main functionality
''' 
class Spoke(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.insert(edit, 0, "HISS HISS I'M A PYTHON!")
