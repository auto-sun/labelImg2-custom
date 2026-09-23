#import json
import pickle
import os
import sys

class Settings(object):
    def __init__(self):
        # Source runs keep their existing settings beside labelImg.py;
        # installed/frozen runs use the writable per-user profile.
        self.data = {}
        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        if getattr(sys, 'frozen', False):
            # Installers normally place program files in a read-only location.
            # Keep each user's preferences outside the installed application.
            app_dir = os.path.join(
                os.environ.get('APPDATA') or
                os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming'),
                'LabelImg2Custom')
        if sys.version_info < (3, 0, 0):
            self.path = os.path.join(app_dir, 'labelImg2Settings2.pkl')
        else:
            self.path = os.path.join(app_dir, 'labelImg2Settings3.pkl')

    def __setitem__(self, key, value):
        self.data[key] = value

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        if key in self.data:
            return self.data[key]
        return default

    def save(self):
        if self.path:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, 'wb') as f:
                pickle.dump(self.data, f, pickle.HIGHEST_PROTOCOL)
                #json.dump(self.data, f)
                return True
        return False

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, 'rb') as f:
                self.data = pickle.load(f)
                #self.data = json.load(f)
                return True
        return False

    def reset(self):
        if os.path.exists(self.path):
            os.remove(self.path)
            print ('Remove setting pkl file ${0}'.format(self.path))
        self.data = {}
        self.path = None
