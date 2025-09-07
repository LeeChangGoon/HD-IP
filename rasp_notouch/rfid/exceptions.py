class CustomException(Exception):
    def __init__(self, message, status_code=500, extra_data=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.extra_data = extra_data if extra_data is not None else {}

    def __str__(self):
        return f"{self.message} (Status Code: {self.status_code})"
