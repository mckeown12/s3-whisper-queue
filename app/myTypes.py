from pydantic import BaseModel
from typing import Union, Literal

class SalesforceTemplate(BaseModel):
    '''template bodies are jinja2 template strings with allowable variables:
            - Transcription
            - Language
            - Translation
            - Subject
            - Description
            - PreferredCallBackTime
            - Sentiment
            - Duration
            - Equipment (a list of dictionaries with keys manufacturer, serial, model)
    '''
    url : str
    body : str
    method : str
    headers: dict[str, str] = {}

class SalesforceRequest(BaseModel):
    salesforce_instance: Union[Literal['ventures'], Literal['bk'], Literal['ce'], Literal['ecmd'], Literal['gmmdmdev'], Literal['cedev'], Literal['gmdevelop']]
    audio_file_id: str
    template: list[SalesforceTemplate]
    transcription: str | None = None
    duration: float | None = None

class SalesforceExternalRequest(BaseModel):
    salesforce_instance: str
    external_file_url: str
    headers: dict = {}
    template: list[SalesforceTemplate]
    transcription: str | None = None
    duration: float | None = None

class GMTranscribeRequest(BaseModel):
    audio_file_url: str
    audio_file_request_headers: dict
    template: list[SalesforceTemplate]
    transcription: str | None = None
    duration: float | None = None