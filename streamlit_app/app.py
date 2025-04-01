import streamlit as st
from mistralai import Mistral
import base64
import os
from dotenv import load_dotenv
import requests
import time

# Load environment variables
load_dotenv()

# Configure page
st.set_page_config(page_title="Storacha RAG Agent", layout="wide")
st.title("🤖 Storacha RAG Agent")

# Initialize Mistral client (for image analysis only)
client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
MODEL_NAME = "pixtral-12b-2409"  # Adjust if needed

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "system",
        "content": "You are a helpful AI assistant with vision capabilities."
    }]
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}
if "settings" not in st.session_state:
    st.session_state.settings = {"safe_mode": True}

# Helper functions for image handling
def encode_image(image_data):
    """Encode image to base64"""
    return base64.b64encode(image_data).decode('utf-8')

def process_uploaded_file(uploaded_file):
    """Process image file for chat"""
    if uploaded_file.type.startswith('image/'):
        base64_image = encode_image(uploaded_file.getvalue())
        return {
            "file_id": uploaded_file.file_id,
            "content": base64_image,
            "file_name": uploaded_file.name,
            "type": "image"
        }
    st.error("Only image files are supported in chat.")
    return None

# Sidebar
with st.sidebar:
    selected_tab = st.radio(
        "Menu",
        ["📚 Knowledge Base"],
        horizontal=True,
        label_visibility="collapsed"
    )

    if selected_tab == "📚 Knowledge Base":
        st.header("Manage Knowledge Base")

        # Text input
        text_input = st.text_area("Enter text to add to knowledge base")
        if st.button("Add Text"):
            if text_input:
                try:
                    response = requests.post(
                        "http://localhost:3000/rag/upload",
                        json={"type": "text", "content": text_input}
                    )
                    if response.status_code == 200:
                        st.success("Text uploaded successfully")
                    else:
                        st.error(f"Failed to upload text: {response.text}")
                except Exception as e:
                    st.error(f"Error uploading text: {str(e)}")

        # URL input
        url_input = st.text_input("Enter URL to add to knowledge base")
        if st.button("Add URL"):
            if url_input:
                try:
                    response = requests.post(
                        "http://localhost:3000/rag/upload",
                        json={"type": "url", "url": url_input}
                    )
                    if response.status_code == 200:
                        st.success("URL uploaded successfully")
                    else:
                        st.error(f"Failed to upload URL: {response.text}")
                except Exception as e:
                    st.error(f"Error uploading URL: {str(e)}")

        # PDF upload
        pdf_file = st.file_uploader("Upload PDF", type=["pdf"])
        if pdf_file:
            progress_text = st.empty()
            progress_bar = st.progress(0)

            try:
                progress_text.text("Step 1: Preparing file...")
                # No delay needed if reading directly
                time.sleep(0.5)
                progress_bar.progress(20)

                progress_text.text("Step 2: Uploading PDF...")
                files = {"file": (pdf_file.name, pdf_file.getvalue(), "application/pdf")}
                data = {"type": "pdf"}
                response = requests.post(
                    "http://localhost:3000/rag/upload",
                    files=files,
                    data=data,
                    timeout=600  # adjust timeout as needed
                )
                progress_bar.progress(80)
                progress_text.text("Step 3: Waiting for response...")
                time.sleep(0.5)  # Simulate time for processing

                if response.status_code == 200:
                    st.success("PDF uploaded successfully!")
                    progress_text.text("Processing complete.")
                else:
                    st.error(f"Failed to upload PDF: {response.text}")
                    progress_text.text("Error during upload.")
            except Exception as e:
                st.error(f"Error uploading PDF: {str(e)}")
                progress_text.text("Upload failed.")
            
            progress_bar.progress(100)



# Display chat history
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            if message["type"] == "text":
                st.markdown(message["content"])
            elif message["type"] == "image":
                st.image(base64.b64decode(message["content"]), caption=message["file_name"])

# Chat input
prompt = st.chat_input(
    "Ask a question or upload image",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"]
)

if prompt:
    # Handle text query
    if prompt.text:
        query = prompt.text
        st.session_state.messages.append({"role": "user", "content": query, "type": "text"})
        with st.chat_message("user"):
            st.markdown(query)
        try:
            response = requests.post(
                "http://localhost:3000/rag/query",
                json={"question": query}
            )
            if response.status_code == 200:
                answer = response.json().get("answer", "No answer received")
                st.session_state.messages.append({"role": "assistant", "content": answer, "type": "text"})
                with st.chat_message("assistant"):
                    st.markdown(answer)
            else:
                st.error(f"Failed to get answer: {response.text}")
        except Exception as e:
            st.error(f"Error querying API: {str(e)}")

    # Handle image upload
    if prompt.files:
        for uploaded_file in prompt.files:
            result = process_uploaded_file(uploaded_file)
            if result:
                st.session_state.uploaded_files[result["file_id"]] = result
                st.session_state.messages.append({
                    "role": "user",
                    "content": result["content"],
                    "type": result["type"],
                    "file_id": result["file_id"],
                    "file_name": result["file_name"]
                })
                with st.chat_message("user"):
                    st.image(base64.b64decode(result["content"]), caption=result["file_name"])
                with st.chat_message("assistant"):
                    try:
                        messages = [
                            {"role": "system", "content": "You are a helpful AI assistant with vision capabilities."},
                            {"role": "user", "content": [
                                {"type": "text", "text": "Analyze this image:"},
                                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{result['content']}"}
                            ]}
                        ]
                        response_placeholder = st.empty()
                        full_response = []
                        stream_response = client.chat.stream(
                            model=MODEL_NAME,
                            messages=messages,
                            safe_prompt=st.session_state.settings["safe_mode"]
                        )
                        for chunk in stream_response:
                            if chunk.data.choices[0].delta.content:
                                content = chunk.data.choices[0].delta.content
                                full_response.append(content)
                                response_placeholder.markdown("".join(full_response) + "▌")
                        response_placeholder.markdown("".join(full_response))
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": "".join(full_response),
                            "type": "text"
                        })
                    except Exception as e:
                        st.error(f"Error generating response: {str(e)}")