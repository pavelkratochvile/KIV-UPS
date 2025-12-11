class LogikClient:
    def __init__(self, socket=None):
        self.socket = socket
        self.name = None
        self.role = None
        print("LogikClient initialized")