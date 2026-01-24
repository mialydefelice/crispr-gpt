from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
except ImportError:
    from langchain.schema import AIMessage, HumanMessage, SystemMessage
import requests
import json
from crisprgpt.safety import WARNING_PRIVACY, contains_identifiable_genes
from util import get_logger
import dotenv
import os

dotenv.load_dotenv()
logger = get_logger(__name__)


class FakeChatOpenAI:  ## For debug purpose only
    def __init__(self, **kwargs):
        pass

    def __call__(self, inputs):
        logger.info("FakeChatOpenAI Called")
        response = input()
        return AIMessage(content=response)

class IdentifiableGeneError(ValueError): pass

class OpenAIChat:
    openai_key = os.getenv("OPENAI_KEY") 

    model4_turbo = ChatOpenAI(openai_api_key=openai_key, model_name = 'gpt-4-turbo')
    model4 = ChatOpenAI(openai_api_key=openai_key, model_name = 'gpt-4o')
    # model3 = ChatOpenAI(openai_api_key=openai_key, model_name = 'gpt-3.5-turbo-0613')
    model3 = ChatOpenAI(openai_api_key=openai_key, model_name = 'gpt-4o')

    model4_turbo_json = model4_turbo.bind(response_format = {"type": "json_object"})
    model4_json = model4.bind(response_format = {"type": "json_object"})


    @classmethod
    def chat(cls, request, use_GPT4=True, use_GPT4_turbo=False):
        if contains_identifiable_genes(request):
            raise IdentifiableGeneError(WARNING_PRIVACY)
        if use_GPT4_turbo:
            response = cls.model4_turbo_json.invoke(request).content
        elif use_GPT4:
            response = cls.model4_json.invoke(request).content
        else:
            response = cls.model3([HumanMessage(content=request)]).content
        logger.info(response)

        ## postprocessing
        response = response.lstrip("```json")
        response = response.lstrip("```")
        response = response.rstrip("```")
        response = response.strip()

        json_response = json.loads(response)
        return json_response

    @classmethod
    def QA(cls, request, use_GPT4=False):
        return "QA is not supported in the lite version."