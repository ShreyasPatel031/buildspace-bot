import os
import tempfile
import streamlit as st
from langchain_community.chat_models import ChatOpenAI
from langchain_community.document_loaders import PyPDFLoader
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.callbacks.base import BaseCallbackHandler
from langchain.chains import ConversationalRetrievalChain
from langchain_community.vectorstores import DocArrayInMemorySearch
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_core.prompts import PromptTemplate
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate



st.set_page_config(page_title="buildspace", page_icon="buildspace_logo.jpeg")


st.image("buildspace_logo.jpeg", width=80, output_format="JPEG")
st.markdown("# buildspace agent")


@st.cache_resource(ttl="1h")
def load_projects(csv_filename):
    # Initialize CSVLoader with the path to the merged CSV file
    loader = CSVLoader(file_path=csv_filename)

    # Load data from CSV file
    data = loader.load()

    return data


@st.cache_resource(ttl="1h")
def setup_retriever():
    csv_filename = "merged_project_details.csv"
    openai_key = st.secrets["shreyas_openai_api_key"]

    # VectorDB setup
    embedding = OpenAIEmbeddings(openai_api_key=openai_key)
    vectordb = Chroma.from_documents(documents=load_projects(csv_filename), embedding=embedding)

    # Define retriever
    retriever = vectordb.as_retriever(search_type="mmr", search_kwargs={"k": 5, "fetch_k": 20})

    return retriever


class StreamHandler(BaseCallbackHandler):
    def __init__(self, container: st.delta_generator.DeltaGenerator, initial_text: str = ""):
        self.container = container
        self.text = initial_text
        self.run_id_ignore_token = None
        self.initial_prompt = ""  # Add an attribute to store the initial prompt


    def on_llm_start(self, serialized: dict, prompts: list, **kwargs):
        # Workaround to prevent showing the rephrased question as output
        if prompts and len(prompts) > 0:
            self.initial_prompt = prompts[0]  # Store the initial prompt
        if prompts[0].startswith("Human"):
            self.run_id_ignore_token = kwargs.get("run_id")
        # print("Initial LLM Prompt:", self.initial_prompt)

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        if self.run_id_ignore_token == kwargs.get("run_id", False):
            return
        self.text += token
        # print("New token from LLM:", token)
        self.container.markdown(self.text)


class PrintRetrievalHandler(BaseCallbackHandler):
    def __init__(self, container):
        self.status = container.status("**retrieving n&w database**")

    def parse_doc_content(self, content):
        """Parse document content string into a dictionary of fields."""
        fields = {}
        for line in content.split('\n'):
            if ': ' in line:
                key, value = line.split(': ', 1)
                fields[key] = value
        return fields

    def on_retriever_start(self, serialized: dict, query: str, **kwargs):
        # Display initial retrieving context message
        self.status.text("Retrieving information for your question...")

    def on_retriever_end(self, documents, **kwargs):
        content = "**Helpful Links:**\n\n"  # Ensure this line is at the very start
        for idx, doc in enumerate(documents):
            print("doc",doc)
            fields = self.parse_doc_content(doc.page_content)
            
            # Access fields with get to avoid KeyError if any field is missing
            title = fields.get('Title', 'Unknown Title')
            description = fields.get('Description', 'No description available')
            youtube_url = fields.get('YouTube URL', '#')
            youtube_title = fields.get('YouTube Title', 'Unknown YouTube Title')

            # Constructing the message content
            project_info = (
                f"**Project {idx + 1}: {title}**\n"
                f"Description: {description}\n"
                f"YouTube Title: {youtube_title}\n"
                f"YouTube Link: [Watch Here]({youtube_url})\n\n"
            )
            content += project_info
        
            # Display the constructed content in the Streamlit container
        self.status.markdown(content, unsafe_allow_html=True)
        # Update the status container with the final content
        self.status.update(state="complete")


openai_api_key = st.secrets["shreyas_openai_api_key"]

retriever = setup_retriever()

# Setup memory for contextual conversation
msgs = StreamlitChatMessageHistory()
memory = ConversationBufferMemory(memory_key="chat_history", chat_memory=msgs, return_messages=True)

# Setup LLM and QA chain
llm = ChatOpenAI(
    model_name="gpt-4-turbo-preview", openai_api_key=openai_api_key, temperature=0, streaming=True, verbose=True
)

# Define your system and user message templates
general_system_template = r"""
You are the buildspace assistant ( not the friendly neighborhood buildspace assistant ). Buildspace is the largest place where you give your idea a shot.
any idea — a hip-hop album, short film, a novel, some indie software, a youtube channel — whatever.no idea is too big or too small.
it all starts with nights & weekends.it's six-weeks where you people start any idea from zero on your nights and weekends, and by the end they have their first fans, revenue, downloads, whatever.
As the buildspace assistant you have two main responsibilities:
1. Help people define their ideas, goals and the help they require.
2. Connnect to people who might be able to help. you have access to all the completed projects from the last two seasons of nights & weekends. Show them the projects and help them connect to the right people.
your conversational tone is relaxed and informal. you are a friend who is here to help. you are not cringe either and you are low-key and cool, you are just a friend trying to help.
also always use lowercase letters, never use uppercase letters.
----
{context}
----
"""
general_user_template = "Question:```{question}```"

# Create message templates
messages = [
    SystemMessagePromptTemplate.from_template(general_system_template),
    HumanMessagePromptTemplate.from_template(general_user_template)
]

# Combine messages into a chat prompt template
qa_prompt = ChatPromptTemplate.from_messages(messages)

qa_chain = ConversationalRetrievalChain.from_llm(
    llm, retriever=retriever, memory=memory, verbose=True, chain_type="stuff",
    combine_docs_chain_kwargs={"prompt": qa_prompt}
)

if len(msgs.messages) == 0 or st.sidebar.button("Clear message history"):
    msgs.clear()
    msgs.add_ai_message("How can I help you?")

avatars = {"human": "user", "ai": "assistant"}
for msg in msgs.messages:
    st.chat_message(avatars[msg.type]).write(msg.content)


if user_query := st.chat_input(placeholder="Ask me anything!"):
    st.chat_message("user").write(user_query)

    with st.chat_message("assistant"):
        retrieval_handler = PrintRetrievalHandler(st.container())
        stream_handler = StreamHandler(st.empty())
        response = qa_chain.run(user_query, callbacks=[retrieval_handler, stream_handler])