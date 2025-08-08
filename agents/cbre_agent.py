# agents/cbre_agent.py

# Import core components from the LangChain framework.
# AgentExecutor: The runtime that executes the agent's decisions.
# create_tool_calling_agent: A function to create the agent's "brain".
from langchain.agents import AgentExecutor, create_tool_calling_agent
# Import the specific Language Model (LLM) we'll use, in this case, Google's Gemini.
from langchain_google_vertexai import ChatVertexAI
# Import tools for building the prompt that instructs the agent.
# ChatPromptTemplate: Structures the instructions for the agent.
# MessagesPlaceholder: A special variable that holds the agent's memory or scratchpad.
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Import the custom tool we built for web scraping and archiving.
from tools.cbre_tool import CbreReportArchiverTool

def create_cbre_agent():
    """Builds and returns the CBRE report archiving agent."""

    # 1. Initialize the Language Model (LLM)
    # This creates an instance of Google's Gemini model.
    # temperature=0 makes the model's responses deterministic and less random.
    llm = ChatVertexAI(model="gemini-1.5-pro-preview-0409", temperature=0)

    # 2. Initialize the Custom Tool
    # This creates an instance of our report archiver tool. The `name` and `description`
    # are critical, as the LLM uses them to understand what the tool does and when to call it.
    cbre_tool = CbreReportArchiverTool(
        name="cbre_report_archiver",
        description=(
            "Searches for and archives CBRE market reports. "
            "If the user's request is broad or does not specify filters like country, "
            "property type, year, or period, this tool MUST be called with its "
            "default parameters to perform a general search."
        )
    )
    # The agent is provided with a list of all available tools.
    tools = [cbre_tool]

    # 3. Create the Agent's Prompt (Its Core Instructions)
    # The prompt template defines the agent's persona, goals, and constraints.
    prompt = ChatPromptTemplate.from_messages([
        # The "system" message contains the main instructions for the agent.
        (
            "system",
            "You are a highly specialized assistant for fetching real estate reports. "
            "Your primary goal is to use the available tools to fulfill the user's request. "
            "Do not make assumptions or question the user's input, such as the requested year. "
            "Trust the user and execute the tool call if possible."
            # These next lines are crucial for controlling the agent's behavior after a tool run.
            "After the tool runs, it will return a summary of what happened. "
            "Your job is to clearly report this summary back to the user. "
            # This defines the "finish" conditions, telling the agent when its job is done.
            "If the summary mentions successful downloads, partial successes (files moved to a failed folder), or that there are no new reports to download, your task is complete. "
            # This is a direct command to prevent the agent from getting into a loop.
            "**Do not run the tool again in the same turn.** Only report the outcome."
        ),
        # This placeholder is where the history of the conversation (tool calls and results) is injected.
        MessagesPlaceholder(variable_name="agent_scratchpad"),
        # This is where the user's specific request (e.g., "download all reports") is inserted.
        ("human", "{input}"),
    ])

    # 4. Create the Agent's "Brain"
    # This function binds the LLM, the list of tools, and the prompt together.
    # The resulting 'agent' is the core logic that decides what action to take.
    agent = create_tool_calling_agent(llm, tools, prompt)

    # 5. Create the Agent Executor (The Runtime)
    # The AgentExecutor takes the agent's decisions and actually runs the tools.
    # It manages the loop of: Agent decides -> Executor runs tool -> Executor returns result to Agent.
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        # verbose=True prints the agent's thought process to the console, which is great for debugging.
        verbose=True,
        # This prevents the agent from crashing if the LLM produces a malformed output.
        handle_parsing_errors=True
    )
    
    # Return the fully configured and runnable agent executor.
    return agent_executor