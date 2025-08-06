# search_tools.py

import os
import requests

from dotenv import load_dotenv
load_dotenv()

from typing import Type
from google import genai
from pydantic_ai import Agent
from google.genai import types
from utils import get_model_name
from pydantic import BaseModel, Field
from langchain.tools.base import StructuredTool
from pydantic_ai.models.gemini import GeminiModel

PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')
LOCATION = os.getenv('LOCATION')

class SearchToolSchema(BaseModel):
    """
    Schema for the input to the SearchTool.

    Attributes:
        query (str): The query to search the web for.
    """
    query: str = Field(
        ...,
        title = "query",
        description = (
            "The query to search the web for."
        )
    )

class StructuredResponse(BaseModel):
    """
    Schema for the structured response from the tool.

    Attributes:
        response (str): The response from the tool.
    """
    response: str = Field(
        ...,
        title = "response",
        description = (
            "The response from the tool."
        )
    )

class SearchToolResponse(BaseModel):
    """
    Schema for the output from the SearchTool.

    Attributes:
        input (str): The input that was sent to the tool.
        searches (list[str]): The searches that were performed to get the response.
        sources (list[str]): The sources of the response (list of URLs).
        response (StructuredResponse): The structured response from the tool.
    """
    input: str = Field(
        ...,
        title = "input",
        description = (
            "The input to the tool."
        )
    )
    searches: list[str] = Field(
        ...,
        title = "searches",
        description = (
            "The searches that were performed to get the response."
        )
    )
    sources: list[str] = Field(
        ...,
        title = "sources",
        description = (
            "The sources of the response."
            "This should be a list of URLs."
        )
    )
    response: StructuredResponse = Field(
        ...,
        title = "response",
        description = (
            "The response from the tool."
        )
    )

class SearchTool(StructuredTool):
    """
    SearchTool is a structured tool that searches the web for information using a Gemini model and Google Search.

    This tool takes a user query as input, performs a web search using Google's search tool, and returns a structured response
    including the searches performed, the sources (URLs) found, and a summarized response. It is designed to be used as a component
    in larger agent or toolchain systems.

    Attributes:
        name (str): The name of the tool.
        model_name (str): The name of the Gemini model to use.
        description (str): A description of the tool.
        handle_tool_error (bool): Whether to handle errors raised by the tool.
        args_schema (Type[BaseModel]): The schema for the tool's input arguments.
        verbose (bool): Whether to print verbose output.
    """
    name: str = "search"
    model_name: str = None
    description: str = (
        "A tool that searches the web for information."
    )
    handle_tool_error: bool = True
    args_schema: Type[BaseModel] = SearchToolSchema
    verbose: bool = True

    def __init__(self, model_name = None, *args, **kwargs):
        """
        Initialize the SearchTool.

        Args:
            model_name (str, optional): The name of the Gemini model to use. If not provided,
                the model name will be determined automatically.
            *args: Additional positional arguments for the parent class.
            **kwargs: Additional keyword arguments for the parent class.
        """
        super().__init__(*args, **kwargs)
        if not model_name:
            self.model_name = get_model_name()
        else:
            self.model_name = model_name

    def _run(self, query: str) -> str:
        """
        Run the tool with the provided query.

        Args:
            query (str): The query to search the web for.

        Returns:
            SearchToolResponse: The structured response containing the input, searches, sources, and response.

        Raises:
            ValueError: If the query is empty.
        """
        print(f'Running tool with query: {query}')
        if not query:
            raise ValueError("Query cannot be empty")

        client = genai.Client(vertexai = True, project = PROJECT_ID, location = LOCATION)

        grounding_tool = types.Tool(
            google_search = types.GoogleSearch()
        )

        grounding_config = types.GenerateContentConfig(
            tools = [grounding_tool],
        )

        grounding_prompt = f"""
        You are a helpful assistant that can search the web for information.
        You will be given a query and you will need to use the internet to find the answer.
        Answer the following question:
        {query}
        """

        grounded_response = client.models.generate_content(
            model = self.model_name,
            contents = grounding_prompt,
            config = grounding_config
        )

        text_to_structure = grounded_response.text
        chunks = grounded_response.candidates[0].grounding_metadata.grounding_chunks
        searches = grounded_response.candidates[0].grounding_metadata.web_search_queries

        uris = [chunk.web.uri for chunk in chunks]
        original_urls = []
        for uri in uris:
            r = requests.get(uri, allow_redirects = True)
            if r.status_code == 200:
                original_url = r.url
            else:
                r = requests.get(uri, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects = True)
                if r.status_code == 200:
                    original_url = r.url
                else:
                    continue
            original_urls.append(original_url)

        structuring_config = types.GenerateContentConfig(
            response_mime_type = 'application/json',
            response_schema = StructuredResponse
        )

        structuring_prompt = f"""
        You are a helpful assistant that can structure the output of a tool.
        You will be given a response from a tool.
        You will need to structure the response into a JSON object.
        ####
        The response is:
        {text_to_structure}
        ####
        """

        structured_response = client.models.generate_content(
            model = self.model_name,
            contents = structuring_prompt,
            config = structuring_config
        )

        return SearchToolResponse(
            input = query,
            searches = searches,
            sources = original_urls,
            response = structured_response.parsed
        )

if __name__ == "__main__":
    """
    Example usage of the SearchTool.
    """
    tool = SearchTool()
    response = tool.run("What is the industrial outlook for Kansas City for Q3 2025?")
    print(response.searches)
    print(response.sources)
    print(response.response.response)