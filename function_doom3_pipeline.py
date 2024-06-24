from pydantic import BaseModel
from typing import Union, Generator, Iterator, Dict
from utils.misc import get_last_user_message
from apps.webui.models.files import Files

import requests
import time
import uuid
import os
import json

from config import UPLOAD_DIR


class Pipe:
    class Valves(BaseModel):
        OPENAI_API_BASE_URL: str = "http://localhost:8080/openai/v1"
        MODEL_NAME: str = "DOOM3:latest"
        AUTH_ENDPOINT: str = os.getenv(
            "AUTH_ENDPOINT", "http://localhost:8080/get-bearer-token"
        )
        GITHUB_REPO_URL: str = (
            "https://raw.githubusercontent.com/justinh-rahb/webui-doom3/build-wasm/"
        )
        DATA_FILE_URL: str = f"{GITHUB_REPO_URL}demo00.data"
        DATA_JS_URL: str = f"{GITHUB_REPO_URL}demo00.js"
        pass

    def __init__(self):
        self.type = "manifold"
        self.valves = self.Valves()
        self.pipes = [{"name": self.valves.MODEL_NAME, "id": self.valves.MODEL_NAME}]
        self.token = None
        pass

    def get_bearer_token(self) -> str:
        try:
            response = requests.post(self.valves.AUTH_ENDPOINT)
            response.raise_for_status()
            self.token = response.json().get("token")
            return self.token
        except requests.RequestException as e:
            raise Exception(f"Error fetching bearer token: {str(e)}")

    def create_file(
        self, file_name: str, title: str, content: Union[str, bytes], content_type: str
    ):
        base_path = UPLOAD_DIR + "/"
        file_id = str(uuid.uuid4())

        file_path = base_path + file_id + "_" + file_name
        # Create a file
        mode = "w" if isinstance(content, str) else "wb"
        with open(file_path, mode) as f:
            f.write(content)

        meta = {
            "source": file_path,
            "title": title,
            "content_type": content_type,
            "size": os.path.getsize(file_path),
            "path": file_path,
        }

        class FileForm(BaseModel):
            id: str
            filename: str
            meta: dict = {}

        formData = FileForm(id=file_id, filename=file_name, meta=meta)

        file = Files.insert_new_file(self.user_id, formData)
        return file.id

    def get_file_url(self, file_id: str) -> str:
        return f"/api/v1/files/{file_id}/content"

    def responses(
        self, command: str, messages: list
    ) -> Union[str, Generator, Iterator]:
        print(f"responses:{__name__}")

        command_body = get_last_user_message(messages)[len(command) + 2 :]
        print("Command Body:", command_body)

        list_of_responses = ["![DOOM3](logo.png)"]

        # Check if the files already exist
        files = Files.get_files()
        files = [file for file in files if file.user_id == self.user_id]

        existing_html = next(
            (file for file in files if "d3wasm.html" in file.filename), None
        )

        if existing_html:
            list_of_responses.append(
                "Looks like you already have the game files... 🤘\n\n"
            )
            list_of_responses.append(
                "{{HTML_FILE_ID_{FILE_ID}}}".replace("{FILE_ID}", existing_html.id)
            )
        else:
            data_file_url = self.valves.DATA_FILE_URL
            data_js_url = self.valves.DATA_JS_URL
            html_url = f"{self.valves.GITHUB_REPO_URL}d3wasm.html"
            js_url = f"{self.valves.GITHUB_REPO_URL}d3wasm.js"
            wasm_url = f"{self.valves.GITHUB_REPO_URL}d3wasm.wasm"

            # Step 1: Download and upload the data file as demo00.data
            list_of_responses.append("```console\nDownloading DATA......... ")
            data_file_id = self.download_and_create_file(
                "demo00.data", data_file_url, "application/octet-stream"
            )
            list_of_responses.append(f"ID: {data_file_id} DONE\n")
            print(f"demo00.data ID: {data_file_id}")

            # Step 2: Download and upload the demo00.js file
            list_of_responses.append("Downloading CFG.......... ")
            data_js_id = self.download_and_create_file(
                "demo00.js", data_js_url, "application/javascript"
            )
            list_of_responses.append(f"ID: {data_js_id} DONE\n")
            print(f"demo00.js ID: {data_js_id}")

            # Step 3: Download and upload the WASM file
            list_of_responses.append("Downloading WASM......... ")
            wasm_id = self.download_and_create_file(
                "d3wasm.wasm", wasm_url, "application/wasm"
            )
            list_of_responses.append(f"ID: {wasm_id} DONE\n")
            print(f"d3wasm.wasm ID: {wasm_id}")

            # Step 4: Download, modify, and upload the JavaScript file
            list_of_responses.append("Downloading JS........... ")
            js_content = requests.get(js_url).text
            js_content = js_content.replace("d3wasm.wasm", self.get_file_url(wasm_id))
            js_content = js_content.replace("demo00.js", self.get_file_url(data_js_id))
            js_id = self.create_file(
                "d3wasm.js",
                "d3wasm.js",
                js_content,
                "application/javascript",
            )
            list_of_responses.append(f"ID: {js_id} DONE\n")
            print(f"d3wasm.js ID: {js_id}")

            # Step 5: Download, modify, and upload the HTML file
            list_of_responses.append("Downloading HTML......... ")
            html_content = requests.get(html_url).text

            html_content = html_content.replace("d3wasm.js", self.get_file_url(js_id))
            html_id = self.create_file(
                "d3wasm.html", "d3wasm.html", html_content, "text/html"
            )
            list_of_responses.append(f"ID: {html_id} DONE\n```\n\n")
            print(f"d3wasm.html ID: {html_id}")

            # Step 6: Provide the final HTML ID to display in iframe
            list_of_responses.append("Time to play... 😈\n\n")
            list_of_responses.append(
                "{{HTML_FILE_ID_{FILE_ID}}}".replace("{FILE_ID}", html_id)
            )

        for response in list_of_responses:
            time.sleep(1)
            yield response

        return "Done"

    def download_and_create_file(self, file_name: str, url: str, content_type: str):
        try:
            response = requests.get(url)
            response.raise_for_status()
            content = response.content

            # Create the file with the correct content type
            return self.create_file(file_name, file_name, content, content_type)
        except Exception as e:
            raise Exception(f"Error handling {file_name}: {str(e)}")

    def pipe(self, body: dict, __user__: dict) -> Union[str, Generator, Iterator]:
        print(f"pipe:{__name__}")

        self.user_id = __user__["id"]

        messages = body["messages"]
        user_message = get_last_user_message(messages)

        if user_message.startswith("/"):
            command = user_message.split(" ")[0][1:]
            print(f"Command: {command}")
            return self.responses(command, messages)
        else:
            print("No command found - calling API")

        headers = {}
        headers["Content-Type"] = "application/json"
        headers["Authorization"] = f"Bearer {self.get_bearer_token()}"

        model_id = body["model"][body["model"].find(".") + 1 :]
        payload = {**body, "model": model_id}

        return self.call_api(body, headers, payload)

    def call_api(
        self, body: dict, headers: dict, payload: dict
    ) -> Union[str, dict, Generator, Iterator]:
        # Call the API based on the API_TYPE
        print(f"call_api:{__name__}")
        print(f"call_api:{body}")

        base_url = self.valves.OPENAI_API_BASE_URL
        endpoint = "/v1/chat/completions"

        try:
            r = requests.post(
                url=f"{base_url}{endpoint}",
                json=payload,
                headers=headers,
                stream=True,
            )

            r.raise_for_status()

            if body["stream"]:
                return r.iter_lines()
            else:
                return r.json()
        except Exception as e:
            return f"Error: {e}"
