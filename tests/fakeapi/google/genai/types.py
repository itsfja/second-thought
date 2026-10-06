"""Minimal stand-ins for the google.genai.types classes the runtime uses."""


class Part:
    def __init__(self, text=None, data=None, mime_type=None):
        self.text, self.data, self.mime_type = text, data, mime_type

    @classmethod
    def from_text(cls, text):
        return cls(text=text)

    @classmethod
    def from_bytes(cls, data, mime_type):
        return cls(data=data, mime_type=mime_type)


class Content:
    role = "user"

    def __init__(self, parts):
        self.parts = parts


class UserContent(Content):
    role = "user"


class ModelContent(Content):
    role = "model"


class GenerateContentConfig:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class GoogleSearch:
    pass


class Tool:
    def __init__(self, google_search=None):
        self.google_search = google_search
