from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tools.cbre_tool import CbreReportArchiverTool

def create_cbre_agent():
    """Builds and returns the CBRE report archiving agent."""

    llm = ChatVertexAI(model="gemini-2.5-pro", temperature=0)
    cbre_tool = CbreReportArchiverTool(
        name="cbre_report_archiver",
        description=(
            "Searches for and archives CBRE market reports. "
            "If the user's request is broad or does not specify filters like country, "
            "property type, year, or period, this tool MUST be called with its "
            "default parameters to perform a general search."
        )
    )
    tools = [cbre_tool]

    # We are providing a custom system prompt to control the agent's behavior.
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a highly specialized assistant for fetching real estate reports. "
            "Your primary goal is to use the available tools to fulfill the user's request. "
            "Do not make assumptions or question the user's input, such as the requested year. "
            "Trust the user and execute the tool call if possible."
            "After the tool runs, it will return a summary of what happened. "
            "Your job is to clearly report this summary back to the user. "
            "If the summary mentions successful downloads, partial successes (files moved to a failed folder), or that there are no new reports to download, your task is complete. "
            "**Do not run the tool again in the same turn.** Only report the outcome."
            "ONLY RUN TOOL ONCE. DO NOT RERUN TOOL AUTOMATICALLY"
        ),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
        ("human", "{input}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        verbose=True, 
        handle_parsing_errors=True
    )
    
    return agent_executor