import os
from langchain_core.messages import HumanMessage
from langchain_core.tools import create_retriever_tool, tool
from langgraph.graph import MessagesState
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_ollama import OllamaEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from .base import get_next_node, make_system_prompt
from dotenv import load_dotenv

load_dotenv()

#embeddings = OllamaEmbeddings(model="qwen3-embedding:8b")
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

index_path = "agents/faiss_index_openai"
if os.path.exists(f"./{index_path}"): 
    db = FAISS.load_local(f"./{index_path}", embeddings, allow_dangerous_deserialization=True)
else:
    loader = PyPDFLoader("./aws-cli.pdf")
    documents = []
    index = 1
    for doc in loader.lazy_load():
        documents.append(doc)
        print(f"Loading page {index}", end='\r')
        index += 1
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    print("Splitting documents into chunks")
    chunks = text_splitter.split_documents(documents)

    print("Embedding documents in vector store")
    batch_size = 100
    db = None # Initialize db outside the loop if it's persistent

    for i in range(0, len(chunks), batch_size):
        if db is None:
            db = FAISS.from_documents(chunks[:batch_size], embeddings)
        else:
            batch = chunks[i:i + batch_size]
            db.add_documents(batch) # Add subsequent batches
        print(f"Processed batch {i // batch_size + 1}/{len(chunks) // batch_size}", end='\r')

    if db == None:
        raise Exception("Sumthing wong")

    db.save_local(f"{index_path}")

retriever = db.as_retriever()

aws_cli_doc_tool = create_retriever_tool(
    retriever,
    "aws_cli_doc_retriever",
    "Searches the AWS CLI documentation for relevant command information and references."
)

llm = ChatOpenAI(model="gpt-4.1-mini")
# llm = ChatOllama(model="qwen3:8b")

command_agent = create_react_agent(
    model=llm,
    tools=[aws_cli_doc_tool],
    prompt=make_system_prompt("""
        You are an agent that resolves cloud security vulnerabilities by suggesting aws cli commands to run in the terminal.
        Explain each step of the solution and keep it simple.
        If you are unsure about how to fix any issues with terminal commands, use your tool to search aws cli documentation for relevant information, DO NOT MAKE UP COMMANDS.
    """),
)

# message = HumanMessage("How do restrict the ip addresses that can access port 22 to 204.98.1.20 for the security group rule sgr-03ecd88d4cab5a8e2")
# msg_state = MessagesState(messages=[message])
# events = command_agent.stream(msg_state, stream_mode='values')
#
# for s in events:
#     print(s["messages"][-1].pretty_print())
#     print("----")

def command_node(state: MessagesState):
    result = command_agent.invoke(state)
    goto = get_next_node(result["messages"][-1], "monitoring")
    result["messages"][-1] = HumanMessage(
        content=result["messages"][-1].content, name="remediation"
    )

    return Command(
        update={"messages": result["messages"]},
        goto=goto,
    )
