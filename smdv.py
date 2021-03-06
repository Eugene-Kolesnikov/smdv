#!/usr/bin/env python3

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

""" smdv: a simple markdown viewer """

## Metadata
__version__ = "0.2.0"
__author__ = "Eugene Kolesnikov"


## Imports

# python standard library
import io
import os
import re
import sys
import json
import time
import socket
import asyncio
import argparse
import warnings
import subprocess
import webbrowser
import collections
import http.client

# 3rd party dependencies
import flask
import websockets
import markdown, mdx_math

MARKDOWN_EXTENSIIONS = [
    mdx_math.MathExtension(enable_dollar_delimiter=True),
    "abbr",
    "attr_list",
    "def_list",
    "fenced_code",
    "footnotes",
    "md_in_html",
    "tables",
    "admonition",
    "codehilite",
    "sane_lists",
    "toc"
]

MD_INTERPRETER = markdown.Markdown(extensions=MARKDOWN_EXTENSIIONS)

# 3rd party CLI dependencies
# fuser
# neovim-remote (to edit files with vim)

## Globals
ARGS = ""  # the smdv command line arguments
SMDV_DEFAULT_ARGS = os.environ.get("SMDV_DEFAULT_ARGS", "")  # default smdv arguments
JSCLIENTS = set()  # jsclients wait for an update from the pyclient
PYCLIENTS = set()  # pyclients update the html body of the jsclient
WEBSOCKETS_SERVER = None  # websockets server
BACKMESSAGES = collections.deque()  # for communication between js and py
FORWARDMESSAGES = collections.deque()  # for communication between js and py
EVENT_LOOP = asyncio.get_event_loop()

MESSAGE = {}

## Templates
HTMLTEMPLATE = """
<!DOCTYPE html>
<html>
    <head>
        <title>smdv {interactive} </title>
        <link rel="stylesheet" href="{md_css_cdn}">
        <style>
            .markdown-body {{
                box-sizing: border-box;
                min-width: 200px;
                max-width: 980px;
                margin: 0 auto;
                padding: 45px;
            }}
            @media (max-width: 767px) {{
                .markdown-body {{
                    padding: 15px;
                }}
            }}
            .tooltip {{
                position: relative;
                display: inline-block;
                color: #006080;
                text-decoration: none;
            }}
            .tooltip .tooltiptext {{
                visibility: hidden;
                position: absolute;
                width: 120px;
                background-color: #555555;
                color: #ffffff;
                text-align: center;
                padding: 5px 0;
                border-radius: 6px;
                z-index: 1;
                opacity: 0;
                transition: opacity 0.3s;
            }}
            .tooltip:hover .tooltiptext {{
                visibility: visible;
                opacity: 1;
            }}
            .tooltip-bottom {{
                top: 135%;
                left: 50%;
                margin-left: -60px;
            }}
            .tooltip-bottom::after {{
                content: "";
                position: absolute;
                bottom: 100%;
                left: 50%;
                margin-left: -5px;
                border-width: 5px;
                border-style: solid;
                border-color: transparent transparent #555555 transparent;
            }}
            .tooltip-left {{
                top: -5px;
                bottom:auto;
                right: 128%;
            }}
            .tooltip-left::after {{
                content: "";
                position: absolute;
                top: 50%;
                left: 100%;
                margin-top: -5px;
                border-width: 5px;
                border-style: solid;
                border-color: transparent transparent transparent #555555;
            }}
            .tooltip-right {{
                top: -5px;
                left: 125%;
            }}
            .tooltip-right::after {{
                content: "";
                position: absolute;
                top: 50%;
                right: 100%;
                margin-top: -5px;
                border-width: 5px;
                border-style: solid;
                border-color: transparent #555555 transparent transparent;
            }}
            #navbar {{
                font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif,Apple Color Emoji,Segoe UI Emoji,Segoe UI Symbol;
                text-align: center;
                height: 23px;
                border-bottom: 1px dotted black;
            }}
            #notNavbar {{
                font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif,Apple Color Emoji,Segoe UI Emoji,Segoe UI Symbol;
                text-align: right;
                height: 0px;
            }}
            .input_area, .output_area{{
              line-height: 1;
            }}

            /* VS Code highlighting */
            .codehilite .hll {{ background-color: #ffffcc }}
            .codehilite  {{ background: #ffffff; }}
            .codehilite .c {{ color: #008000 }} /* Comment */
            .codehilite .err {{ border: 1px solid #FF0000 }} /* Error */
            .codehilite .k {{ color: #0000ff }} /* Keyword */
            .codehilite .ch {{ color: #008000 }} /* Comment.Hashbang */
            .codehilite .cm {{ color: #008000 }} /* Comment.Multiline */
            .codehilite .cp {{ color: #0000ff }} /* Comment.Preproc */
            .codehilite .cpf {{ color: #008000 }} /* Comment.PreprocFile */
            .codehilite .c1 {{ color: #008000 }} /* Comment.Single */
            .codehilite .cs {{ color: #008000 }} /* Comment.Special */
            .codehilite .ge {{ font-style: italic }} /* Generic.Emph */
            .codehilite .gh {{ font-weight: bold }} /* Generic.Heading */
            .codehilite .gp {{ font-weight: bold }} /* Generic.Prompt */
            .codehilite .gs {{ font-weight: bold }} /* Generic.Strong */
            .codehilite .gu {{ font-weight: bold }} /* Generic.Subheading */
            .codehilite .kc {{ color: #0000ff }} /* Keyword.Constant */
            .codehilite .kd {{ color: #0000ff }} /* Keyword.Declaration */
            .codehilite .kn {{ color: #0000ff }} /* Keyword.Namespace */
            .codehilite .kp {{ color: #0000ff }} /* Keyword.Pseudo */
            .codehilite .kr {{ color: #0000ff }} /* Keyword.Reserved */
            .codehilite .kt {{ color: #2b91af }} /* Keyword.Type */
            .codehilite .s {{ color: #a31515 }} /* Literal.String */
            .codehilite .nc {{ color: #2b91af }} /* Name.Class */
            .codehilite .ow {{ color: #0000ff }} /* Operator.Word */
            .codehilite .sa {{ color: #a31515 }} /* Literal.String.Affix */
            .codehilite .sb {{ color: #a31515 }} /* Literal.String.Backtick */
            .codehilite .sc {{ color: #a31515 }} /* Literal.String.Char */
            .codehilite .dl {{ color: #a31515 }} /* Literal.String.Delimiter */
            .codehilite .sd {{ color: #a31515 }} /* Literal.String.Doc */
            .codehilite .s2 {{ color: #a31515 }} /* Literal.String.Double */
            .codehilite .se {{ color: #a31515 }} /* Literal.String.Escape */
            .codehilite .sh {{ color: #a31515 }} /* Literal.String.Heredoc */
            .codehilite .si {{ color: #a31515 }} /* Literal.String.Interpol */
            .codehilite .sx {{ color: #a31515 }} /* Literal.String.Other */
            .codehilite .sr {{ color: #a31515 }} /* Literal.String.Regex */
            .codehilite .s1 {{ color: #a31515 }} /* Literal.String.Single */
            .codehilite .ss {{ color: #a31515 }} /* Literal.String.Symbol */

            @font-face {{
                font-family: "Material Icons";
                font-style: normal;
                font-weight: 400;
                src: local("Material Icons"), local("MaterialIcons-Regular"), url("data:application/x-font-woff;charset=utf-8;base64,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") format("woff");
            }}

            .admonition {{
                box-shadow: 0 2px 2px 0 rgba(0, 0, 0, .14), 0 1px 5px 0 rgba(0, 0, 0, .12), 0 3px 1px -2px rgba(0, 0, 0, .2);
                position: relative;
                margin: 1.5625em 0;
                padding: 0 1.2rem;
                border-left: .4rem solid rgba(68, 138, 255, .8);
                border-radius: .2rem;
                background-color: rgba(255, 255, 255, 0.05);
                overflow: auto;
            }}

            .admonition>.admonition-title {{
                margin: 0 -1.2rem;
                padding: .8rem 1.2rem .8rem 3.6rem;
                margin-bottom: 15px;
                border-bottom: 1px solid rgba(68, 138, 255, .2);
                background-color: rgba(68, 138, 255, .1);
                font-weight: 700;
            }}

            .admonition>.admonition-title:before {{
                position: absolute;
                left: 1.2rem;
                font-size: 1.5rem;
                color: rgba(68, 138, 255, .8);
                content: "\E3C9";
            }}

            .admonition>.admonition-title:before {{
                font-family: Material Icons;
                font-style: normal;
                font-variant: normal;
                font-weight: 400;
                line-height: 2rem;
                text-transform: none;
                white-space: nowrap;
                speak: none;
                word-wrap: normal;
                direction: ltr;
            }}

            .admonition.summary,
            .admonition.abstract,
            .admonition.tldr {{
                border-left-color: rgba(0, 176, 255, .8);
            }}

            .admonition.summary>.admonition-title,
            .admonition.abstract>.admonition-title,
            .admonition.tldr>.admonition-title {{
                background-color: rgba(0, 176, 255, .1);
                border-bottom-color: rgba(0, 176, 255, .2);
            }}

            .admonition.summary>.admonition-title:before,
            .admonition.abstract>.admonition-title:before,
            .admonition.tldr>.admonition-title:before {{
                color: rgba(0, 176, 255, 1);
                ;
                content: "\E8D2";
            }}

            .admonition.hint,
            .admonition.tip {{
                border-left-color: rgba(0, 191, 165, .8);
            }}

            .admonition.hint>.admonition-title,
            .admonition.tip>.admonition-title {{
                background-color: rgba(0, 191, 165, .1);
                border-bottom-color: rgba(0, 191, 165, .2);
            }}

            .admonition.hint>.admonition-title:before,
            .admonition.tip>.admonition-title:before {{
                color: rgba(0, 191, 165, 1);
                content: "\E80E";
            }}

            .admonition.info,
            .admonition.todo {{
                border-left-color: rgba(0, 184, 212, .8);
            }}

            .admonition.info>.admonition-title,
            .admonition.todo>.admonition-title {{
                background-color: rgba(0, 184, 212, .1);
                border-bottom-color: rgba(0, 184, 212, .2);
            }}

            .admonition.info>.admonition-title:before,
            .admonition.todo>.admonition-title:before {{
                color: rgba(0, 184, 212, 1);
                ;
                content: "\E88E";
            }}

            .admonition.success,
            .admonition.check,
            .admonition.done {{
                border-left-color: rgba(0, 200, 83, .8);
            }}

            .admonition.success>.admonition-title,
            .admonition.check>.admonition-title,
            .admonition.done>.admonition-title {{
                background-color: rgba(0, 200, 83, .1);
                border-bottom-color: rgba(0, 200, 83, .2);
            }}

            .admonition.success>.admonition-title:before,
            .admonition.check>.admonition-title:before,
            .admonition.done>.admonition-title:before {{
                color: rgba(0, 200, 83, 1);
                ;
                content: "\E876";
            }}

            .admonition.question,
            .admonition.help,
            .admonition.faq {{
                border-left-color: rgba(100, 221, 23, .8);
            }}

            .admonition.question>.admonition-title,
            .admonition.help>.admonition-title,
            .admonition.faq>.admonition-title {{
                background-color: rgba(100, 221, 23, .1);
                border-bottom-color: rgba(100, 221, 23, .2);
            }}

            .admonition.question>.admonition-title:before,
            .admonition.help>.admonition-title:before,
            .admonition.faq>.admonition-title:before {{
                color: rgba(100, 221, 23, 1);
                ;
                content: "\E887";
            }}

            .admonition.warning,
            .admonition.attention,
            .admonition.caution {{
                border-left-color: rgba(255, 145, 0, .8);
            }}

            .admonition.warning>.admonition-title,
            .admonition.attention>.admonition-title,
            .admonition.caution>.admonition-title {{
                background-color: rgba(255, 145, 0, .1);
                border-bottom-color: rgba(255, 145, 0, .2);
            }}

            .admonition.attention>.admonition-title:before {{
                color: rgba(255, 145, 0, 1);
                content: "\E417";
            }}

            .admonition.warning>.admonition-title:before,
            .admonition.caution>.admonition-title:before {{
                color: rgba(255, 145, 0, 1);
                content: "\E002";
            }}

            .admonition.failure,
            .admonition.fail,
            .admonition.missing {{
                border-left-color: rgba(255, 82, 82, .8);
            }}

            .admonition.failure>.admonition-title,
            .admonition.fail>.admonition-title,
            .admonition.missing>.admonition-title {{
                background-color: rgba(255, 82, 82, .1);
                border-bottom-color: rgba(255, 82, 82, .2);
            }}

            .admonition.failure>.admonition-title:before,
            .admonition.fail>.admonition-title:before,
            .admonition.missing>.admonition-title:before {{
                color: rgba(255, 82, 82, 1);
                ;
                content: "\E14C";
            }}

            .admonition.danger,
            .admonition.error,
            .admonition.bug {{
                border-left-color: rgba(255, 23, 68, .8);
            }}

            .admonition.danger>.admonition-title,
            .admonition.error>.admonition-title,
            .admonition.bug>.admonition-title {{
                background-color: rgba(255, 23, 68, .1);
                border-bottom-color: rgba(255, 23, 68, .2);
            }}

            .admonition.danger>.admonition-title:before {{
                color: rgba(255, 23, 68, 1);
                content: "\E3E7";
            }}

            .admonition.error>.admonition-title:before {{
                color: rgba(255, 23, 68, 1);
                content: "\E14C";
            }}

            .admonition.bug>.admonition-title:before {{
                color: rgba(255, 23, 68, 1);
                content: "\E868";
            }}

            .admonition.example,
            .admonition.snippet {{
                border-left-color: rgba(0, 184, 212, .8);
            }}

            .admonition.example>.admonition-title,
            .admonition.snippet>.admonition-title {{
                background-color: rgba(0, 184, 212, .1);
                border-bottom-color: rgba(0, 184, 212, .2);
            }}

            .admonition.example>.admonition-title:before,
            .admonition.snippet>.admonition-title:before {{
                color: rgba(0, 184, 212, 1);
                ;
                content: "\E242";
            }}

            .admonition.quote,
            .admonition.cite {{
                border-left-color: rgba(158, 158, 158, .8);
            }}

            .admonition.quote>.admonition-title,
            .admonition.cite>.admonition-title {{
                background-color: rgba(158, 158, 158, .1);
                border-bottom-color: rgba(158, 158, 158, .2);
            }}

            .admonition.quote>.admonition-title:before,
            .admonition.cite>.admonition-title:before {{
                color: rgba(158, 158, 158, 1);
                ;
                content: "\E244";
            }}
        </style>
        <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
        <script>
            window.MathJax = {{
                tex: {{
                    inlineMath: [['$', '$'], ['\\(', '\\)']]
                }}
            }};
        </script>
    </head>
    <body>
        <div id="navbar">
            <div style="float: left;">
                <span id="closeFile"></span>
                <span id="backButton"></span>
                <span id="upDirectory"></span>
                <span id="homeButton"></span>
                <span id="refreshButton"></span>
                <span id="currentDirectory"></span>
                <span id="directoryLocation"></span>
                <span id="showFile"></span>
                <span id="fileLocation"></span>
                <span id="encodingType"></span>
                <span id="editFile"></span>
            </div>
            &nbsp;
            <div style="float: right;">
                <span id="hideNavbar"></span>
            </div>
        </div>
        <div id="notNavbar">
            <div style="float: right;">
                <span id="showNavbar"></span>
            </div>
        </div>
        <div class="markdown-body" id="content"></div>
        <script>
            // global variables
            var message = {{}};
            var home = "{home}";
            var websocket = new WebSocket("ws://{host}:{port}/");

            // navbar elements
            var showNavIf = function(element, condition, icon, tooltiptext, tooltipClass="tooltip-bottom", separator="&nbsp;\\n"){{ // &middot;
                element.innerHTML = (condition) ? separator + "<a href=\\"#\\" class=\\"tooltip\\">"+icon+"<span class=\\"tooltiptext " + tooltipClass +"\\">" + tooltiptext + "</span></a>" : "";
                element.style.display = (condition) ? "inline" : "none"
            }}

            // logging
            var log_message = function() {{
                for (var key in message) {{
                    console.log(key, ":", message[key].toString().slice(0,20));
                }}
                console.log("\\n");
            }}

            // navbar
            var updateNavbar = function () {{
                var navbarIsHidden = (localStorage.navbarIsHidden == "true") ? true : false;
                navbar.style.display = (navbarIsHidden) ? "none" : "block";
                showNavIf(hideNavbar, !navbarIsHidden, "➖", "hide navbar", tooltipClass="tooltip-left");
                showNavIf(showNavbar, navbarIsHidden, "➕", "show navbar", tooltipClass="tooltip-left");
                showNavIf(closeFile, (message.fileOpen), "✖", "close file", tooltipClass="tooltip-right");
                showNavIf(homeButton, (message.cwd != "/" && !message.fileOpen), "🏠", "home", tooltipClass="tooltip-right");
                showNavIf(backButton, (!message.fileOpen), "⬅", "back", tooltipClass="tooltip-right");
                showNavIf(upDirectory, (message.cwd != "/" && !message.fileOpen), "⬆", "folder up", tooltipClass="tooltip-right");
                showNavIf(currentDirectory, true, "📁", "folder view", tooltipClass = "tooltip-right");
                showNavIf(directoryLocation, true, message.cwd, home+message.cwd, tooltipClass = "tooltip-bottom", separator="");
                showNavIf(showFile, message.filename, "📄", "file view", tooltipClass = "tooltip-bottom");
                filenameTooltip = (message.filename == "@pipe") ? "content piped into smdv" : (message.filename == "@put") ? "content placed by PUT request": home + message.fileCwd + message.filename;
                showNavIf(fileLocation, message.filename, message.filename, filenameTooltip, tooltipClass = "tooltip-bottom", separator="");
                showNavIf(encodingType, (message.fileEncoding && message.fileOpen), "["+message.fileEncoding+"]", "file encoding", tooltipClass = "tooltip-bottom");
                showNavIf(editFile, (message.fileOpen && message.filename != "@pipe" && message.filename != "@put"), "🖋", "edit", tooltipClass = "tooltip-bottom");
            }}

            // body
            var updateBody = function () {{
                if (message.fileOpen) {{
                    document.getElementById("content").innerHTML = message.fileBody;
                }} else {{
                    document.getElementById("content").innerHTML = message.cwdBody;
                }}
                MathJax.typeset()
            }}

            // activate navbar
            window.onload = function() {{
                updateNavbar();
                history.pushState({{}}, "", "/");
            }}

            // send message via websocket
            sendMessage = function(msg) {{
                msg.client = "js";
                websocket.send(JSON.stringify(msg));
            }}

            // websockets
            websocket.onopen = function() {{
                // on first connection, let server know there is a new client
                sendMessage({{"func":"newjsclient"}});
            }}
            websocket.onmessage = function (event) {{
                // parse message
                message = JSON.parse(event.data);
                localStorage.pressedButton = "false";

                // update page
                updateBody()
                updateNavbar()

                // change browser url
                // history.pushState({{}}, '');
                url = (message.fileOpen) ? message.cwd + message.filename : message.cwd
                history.pushState({{url:url}}, url, url);
                // window.history.replaceState({{}}, "", url);

                // scroll marker into view
                marker = document.getElementById("marker");
                if (marker) {{
                     marker.scrollIntoView();
                }}
            }}

            // navbar
            homeButton.onclick = function() {{
                if (message.cwd != "/") {{
                    message.func = "dir";
                    message.cwd = "/";
                    message.cwdBody = "";
                    message.cwdEncoded = false;
                    message.fileOpen = false;
                    sendMessage(message);
                }}
            }}
            backButton.onclick = function() {{
                sendMessage({{"func":"back"}});
            }}
            currentDirectory.onclick = directoryLocation.onclick = function() {{
                if (message.fileOpen) {{
                    message.func = "dir";
                    message.fileOpen = false;
                    sendMessage(message);
                }}
            }}
            showFile.onclick = fileLocation.onclick = function() {{
                if (!message.fileOpen) {{
                    message.fileOpen = true;
                    message.cwd = message.fileCwd;
                    message.cwdEncoded = false;
                    sendMessage(message);
                }}
            }}
            upDirectory.onclick = function() {{
                if (!message.fileOpen) {{
                    message.func = "dir";
                    message.cwd = message.cwd.slice(0, message.cwd.slice(0, -1).lastIndexOf("/"))+"/";
                    message.cwdBody = "";
                    message.cwdEncoded = false;
                    message.fileOpen = false;
                    sendMessage(message);
                }}
            }}
            closeFile.onclick = function() {{
                if (message.fileOpen) {{
                    message.func = "dir";
                    message.fileOpen = false;
                    message.filename = "";
                    message.fileBody = "";
                    message.fileCwd = "";
                    message.fileEncoding = "";
                    message.fileOpen = false;
                    message.forceClose = true;
                    sendMessage(message);
                }}
            }}
            showNavbar.onclick = hideNavbar.onclick = function() {{
                localStorage.navbarIsHidden = (localStorage.navbarIsHidden == "true") ? "false" : "true";
                window.onload();
            }}
            encodingType.onclick = function() {{
            }}
            editFile.onclick = function() {{
                sendMessage({{"func":"editFile"}});
            }}

        </script>
    </body>
</html>
"""


## Async functions (alphabetic)

# as number of js clients
async def ask_num_js_clients():
    """ ask the number of js clients from the websocket server """
    async with websockets.connect(
        f"ws://{ARGS.websocket_host}:{ARGS.websocket_port}"
    ) as websocket:
        await websocket.send(json.dumps({"client": "py", "func": "numJSClients"}))
        num_clients = await websocket.recv()
    return int(num_clients)


# handle a message sent by one of the clients:
async def handle_message(client: websockets.WebSocketServerProtocol, message: str):
    """ handle a message sent by one of the clients

    Args:
        message: the message to update the global message with
    """
    func = message.get("func")
    ARGS.nvim_address = message.pop("nvimAddress", ARGS.nvim_address)
    validate_message(message)
    if "cwd" in message:
        os.chdir(ARGS.home + message["cwd"])
    if not func:
        return
    if func == "numJSClients":
        await client.send(str(len(JSCLIENTS)))
        return
    if func == "editFile":
        edit_in_neovim(ARGS.home + MESSAGE["fileCwd"] + MESSAGE["filename"])
        return
    if func == "back":
        if len(BACKMESSAGES) < 2:
            return
        if message.get("fileOpen"):
            message = BACKMESSAGES.popleft()
        else:
            FORWARDMESSAGES.appendleft(BACKMESSAGES.popleft())
            message = BACKMESSAGES.popleft()
        if len(FORWARDMESSAGES) > 20:
            FORWARDMESSAGES.pop()
        await handle_message(client, message)
        return
    if func == "dir":
        if (
            not message.get("filename")
            and MESSAGE.get("filename")
            and not message.pop("forceClose", False)
        ):
            message["filename"] = MESSAGE["filename"]
            message["fileCwd"] = MESSAGE["fileCwd"]
            message["fileBody"] = MESSAGE["fileBody"]
            message["fileEncoding"] = MESSAGE["fileEncoding"]
            message["fileEncoded"] = MESSAGE["fileEncoded"]
        if not message["cwdEncoded"]:
            message["cwdBody"] = dir2body(message["cwd"])
            message["cwdEncoded"] = True
    if func == "file":
        encode(message)
    if func in {"dir", "file"}:
        MESSAGE.update(message)
        if ARGS.interactive and MESSAGE["func"]=="file":
            edit_in_neovim(ARGS.home + MESSAGE["fileCwd"] + MESSAGE["filename"])
        await send_message_to_all_js_clients()
        return


# register websocket client
async def register_client(client: websockets.WebSocketServerProtocol):
    """ register a client

    This function registers a client (websocket) in either the set of
    javascript sockets or the list of python sockets.  The javascript
    socket should identify itself by sending the message 'js' on load.
    The Python socket on the other hand sends the html body, which
    will be transmitted to all connected javascript sockets.

    Args:
        client: the client (websocket) to register.

    """
    message = await client.recv()
    message = json.loads(message)
    clienttype = message.get("client", "")
    if clienttype == "js":
        JSCLIENTS.add(client)
        await client.send(json.dumps(MESSAGE))
    elif clienttype == "py":
        PYCLIENTS.add(client)
    else:
        raise ValueError("not a valid client identifier specified.")
    await handle_message(client, message)


# python websocket client
async def send_as_pyclient_async(message: dict):
    """ send a message to the smdv server as the python client

    Args:
        message: the message to send (in dictionary format)
    """
    message["client"] = "py"
    async with websockets.connect(
        f"ws://{ARGS.websocket_host}:{ARGS.websocket_port}"
    ) as websocket:
        await websocket.send(json.dumps(message))


# serve clients
async def serve_client(client: websockets.WebSocketServerProtocol, path: str):
    """ asynchronous websocket server to serve a websocket client

    Args:
        client: the client (websocket) to serve.
        path: the path over which to serve

    """
    await register_client(client)
    try:
        async for message in client:
            await handle_message(client, json.loads(message))
    finally:
        await unregister_client(client)


# send updated body contents to javascript clients
async def send_message_to_all_js_clients():
    """ send a message to all js clients

    Args:
        message: dict: the message to send

    """
    if (not BACKMESSAGES) or (MESSAGE["cwd"] != BACKMESSAGES[0]["cwd"]):
        BACKMESSAGES.appendleft(
            {
                "client": "py",
                "func": "dir",
                "cwd": MESSAGE["cwd"],
                "cwdBody": MESSAGE["cwdBody"],
                "cwdEncoded": MESSAGE["cwdEncoded"],
                "filename": "",
                "fileBody": "",
                "fileCwd": "",
                "fileOpen": False,
                "fileEncoding": "",
                "fileEncoded": False,
            }
        )
        if len(BACKMESSAGES) > 20:
            BACKMESSAGES.pop()
    if JSCLIENTS:
        await asyncio.wait([client.send(json.dumps(MESSAGE)) for client in JSCLIENTS])


# unregister websocket client
async def unregister_client(client: websockets.WebSocketServerProtocol):
    """ unregister a client

    Args:
        client: the client (websocket) to unregister.

    """
    if client in JSCLIENTS:
        JSCLIENTS.remove(client)
    if client in PYCLIENTS:
        PYCLIENTS.remove(client)


## Normal functions (alphabetic)

# function to change the current working directory
def change_current_working_directory(path: str) -> str:
    """ change the current working directory

    Args:
        path: filename or directory name. If a filename is given,
            the current directory will be changed to the containing
            folder
    """
    i = 1 if (path and path[0] == "/") else 0
    fullpath = os.path.join(ARGS.home, path[i:])
    filename = ""
    dirpath = fullpath
    if not os.path.isdir(fullpath):
        filename = os.path.basename(fullpath)
        dirpath = os.path.dirname(fullpath)
    if dirpath.endswith("/"):
        dirpath = dirpath[:-1]
    cwd = os.path.abspath(os.getcwd())
    if cwd.endswith("/"):
        cwd = cwd[:-1]
    if not os.path.isdir(dirpath):
        raise FileNotFoundError(f"Could not find directory {dirpath}")
    if not os.path.exists(fullpath) and filename not in ["@pipe", "@put"]:
        raise FileNotFoundError(f"Could not find file {fullpath}")
    if cwd != dirpath:
        os.chdir(dirpath)
    cwd = os.path.abspath(os.getcwd()) + "/"
    cwd = cwd[len(ARGS.home) :]
    return cwd, filename


# flask app factory
def create_app() -> flask.Flask:
    """ flask app factory

    Returns:
        app: the flask app

    """

    app = flask.Flask(__name__, static_folder=ARGS.home, static_url_path="/@static")

    # stop the flask server
    def stop_flask_server() -> int:
        """ stop the flask server

        Returns:
            exit_status: exit status of the request (0: success, 1: failure)

        """
        func = flask.request.environ.get("werkzeug.server.shutdown")
        try:
            func()
            return 0
        except Exception as e:
            return 1

    # index route for the smdv app
    @app.route("/", methods=["GET", "PUT", "DELETE"])
    @app.route("/<path:path>/", methods=["GET"])
    def index(path: str = "") -> str:
        """ the main (index) route of smdv

        Returns:
            html: the html representation of the requested path
        """
        if flask.request.method == "GET":
            try:
                cwd, filename = change_current_working_directory(path)
            except FileNotFoundError:
                return flask.abort(404)

            html = HTMLTEMPLATE.format(
                home=ARGS.home,
                interactive=f"{'--interactive' if ARGS.interactive else ''}",
                md_css_cdn=ARGS.md_css_cdn,
                host=ARGS.websocket_host,
                port=ARGS.websocket_port,
            )
            if filename:
                if is_binary_file(filename):
                    return flask.redirect(flask.url_for("static", filename=path))
                with open(filename, "r") as file:
                    send_as_pyclient(
                        {
                            "func": "file",
                            "cwd": cwd,
                            "cwdBody": dir2body(cwd),
                            "cwdEncoded": True,
                            "filename": filename,
                            "fileBody": file.read(),
                            "fileCwd": cwd,
                            "fileOpen": True,
                            "fileEncoding": "",
                            "fileEncoded": False,
                        }
                    )
                    return html
            # this only happens if requested path is a directory
            send_as_pyclient(
                {
                    "func": "dir",
                    "cwd": cwd,
                    "cwdBody": dir2body(cwd),
                    "cwdEncoded": True,
                    "filename": filename,
                    "fileBody": "",
                    "fileCwd": cwd,
                    "fileOpen": False,
                    "fileEncoding": "",
                    "fileEncoded": False,
                }
            )
            return html

        if flask.request.method == "PUT":
            cwd = (
                os.path.abspath(os.path.expanduser(os.getcwd()))[len(ARGS.home) :] + "/"
            )
            send_as_pyclient(
                {
                    "func": "file",
                    "cwd": cwd,
                    "cwdBody": dir2body(cwd),
                    "cwdEncoded": True,
                    "filename": "@put",
                    "fileBody": flask.request.data.decode(),
                    "fileCwd": cwd,
                    "fileOpen": True,
                    "fileEncoding": "md",
                    "fileEncoded": False,
                }
            )
            return ""

        if flask.request.method == "DELETE":
            exit_status = stop_flask_server()
            return "failed.\n" if exit_status else "success.\n"

        # should never get here:
        return "failed.\n"

    return app


# encode a string in the given encoding format
def encode(message: dict) -> dict:
    """ encode the body of a message. """
    if message.get("fileEncoded", False):
        return message  # don't encode again if the message is already encoded
    message["fileEncoded"] = True
    encoding = message.get("fileEncoding")
    filename = message.get("filename")
    if not encoding:
        if filename[0] == "." and not "." in filename[1:]:
            encoding = "txt"
        else:
            encoding = os.path.splitext(message.get("filename"))[1][1:]
            if not encoding:
                encoding = ARGS.stdin
        message["fileEncoding"] = encoding
    if encoding == "md":
        message["fileBody"] = md2body(message["fileBody"])
        return message
    if encoding == "ipynb":
        try:
            message["fileBody"] = ipynb2body(message["fileBody"])
            return message
        except ImportError:
            encoding = message["fileEncoding"] = "txt"
    if encoding == "txt":
        message["fileBody"] = txt2body(message["fileBody"])
        return message
    if message["fileEncoding"] == "html":
        return message

    message["fileEncoding"] = "txt"
    message["fileEncoded"] = False
    return encode(message)


# convert a directory path to a markdown representation of the directory view
def dir2body(cwd: str) -> str:
    """ convert a directory path to a markdown representation of the directory view

    Args:
        cwd: str: the current working directory path to convert to html

    Returns:
        html: str: the resulting html
    """
    i = 1 if (cwd and cwd[0] == "/") else 0
    path = os.path.join(ARGS.home, cwd[i:])
    paths = sorted([p for p in os.listdir(path)], key=str.upper)
    paths = [os.path.join(path, p) for p in paths]
    url = lambda path: path.replace(ARGS.home, f"http://127.0.0.1:{ARGS.port}")
    link = lambda i, t, p: (f"{t}{i}&nbsp;{os.path.basename(p)}{t[0]}/{t[1:]}", url(p))
    dirlinks = [link("📁", "<b>", p) for p in paths if os.path.isdir(p)]
    filelinks = [link("📄", " ", p) for p in paths if not os.path.isdir(p)]
    dirhtml = [f'<a href="{url}">{name}</a>' for name, url in dirlinks]
    filehtml = [
        f'<a href="{url}">{name.replace("/","")}</a>' for name, url in filelinks
    ]
    html = "<br>\n".join(dirhtml + filehtml)
    return html


# open file in neovim
def edit_in_neovim(filename: str = ""):
    """ Open file in neovim using neovim-remote

    Args:
        filename: str="": the filename to open in neovim
    """
    path = os.path.abspath(os.path.expanduser(filename))
    if not os.path.exists(path):
        return
    sock = ARGS.nvim_address.strip()
    if not ":" in sock:  # unix socket
        dirname = os.path.dirname(sock)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
    if socket_in_use(sock):
        subprocess.Popen(["nvr", "-s", "--nostart", "--servername", sock, path])
    else:
        subprocess.Popen([ARGS.terminal, "-e", "nvr", "-s", "--servername", sock, path])


# convert a jupyter notebook to html
def ipynb2body(content: str) -> str:
    """ convert jupyter notebook

    TODO: make this work from stdin

    Args:
        content: the notebook contents to convert

    Returns:
        html: str: the html representation for the requested jupyter notebook file.

    Note:
        this function requires nbconvert

    """
    from nbconvert.nbconvertapp import NbConvertApp
    from nbconvert.exporters.html import HTMLExporter

    # create an NbConvertApp:
    app = NbConvertApp.instance()
    # initialize the app with the arguments
    app.initialize(["--template=basic"])
    # create an exporter
    app.exporter = HTMLExporter(config=app.config)
    # get html output
    html, _ = app.export_single_notebook(
        notebook_filename=None, resources=None, input_buffer=io.StringIO(content)
    )
    return html


# check if a file is a binary
def is_binary_file(filename: str) -> bool:
    """ check if a file can be considered a binary file

    Args:
        filename: str: the filename of the file to check

    Returns:
        is_binary_string: bool: the truth value indicating wether the file is
            binary or not.
    """
    textchars = (
        bytearray([7, 8, 9, 10, 12, 13, 27])
        + bytearray(range(0x20, 0x7F))
        + bytearray(range(0x80, 0x100))
    )
    is_binary_string = lambda bytes: bool(bytes.translate(None, textchars))

    if not os.path.exists(filename):
        return False

    if is_binary_string(open(filename, "rb").read(1024)):
        return True
    else:
        return False


# kill the websocket server
def kill_websocket_server() -> int:
    """ kills the websocket server

    TODO: find a way to do this more gracefully.

    Returns:
        exit_status: the exit status of the subprocess `fuser -k` system call
    """
    exit_status = subprocess.call(["fuser", "-k", f"{ARGS.websocket_port}/tcp"])
    return exit_status


# ask the number of
def number_of_connected_jsclients():
    """ ask the websocket server for the number of connected js clients """
    return EVENT_LOOP.run_until_complete(ask_num_js_clients())


# main smdv program
def main() -> int:
    """ The main smdv program

    Returns:
        exit_status: the exit status of smdv.
    """
    global ARGS
    try:
        default_args = parse_args(SMDV_DEFAULT_ARGS.split(" "))
        ARGS = parse_args(sys.argv[1:], **default_args.__dict__)

        # first do single-shot smdv flags:
        if ARGS.start_server:
            run_flask_server()
            return 0
        if ARGS.stop_server:
            exit_status = send_delete_request_to_server()
            return exit_status
        if ARGS.start_websocket_server:
            run_websocket_server()
            return 0
        if ARGS.stop_websocket_server:
            exit_status = kill_websocket_server()
            return exit_status
        if ARGS.start:
            run_server_in_subprocess(server="flask")
            run_server_in_subprocess(server="websocket")
            return 0
        if ARGS.stop:
            exit_status1 = send_delete_request_to_server()
            exit_status2 = kill_websocket_server()
            exit_status = exit_status1 + exit_status2
            return exit_status
        if ARGS.server_status:
            print(request_server_status(server="flask"))
            return 0
        if ARGS.websocket_server_status:
            print(request_server_status(server="websocket"))
            return 0

        # first, start websocket server. Assume the server is already running on failure
        if ARGS.restart:  # force restart
            kill_websocket_server()
            wait_for_server(server="websocket", status="stopped")
        run_server_in_subprocess(server="websocket")

        # next, start smdv server. Assume the server is already running on failure
        if ARGS.restart:  # force restart
            send_delete_request_to_server()
            wait_for_server(server="flask", status="stopped")
        run_server_in_subprocess(server="flask")

        # wait for the websocket server to be fully started:
        wait_for_server(server="websocket", status="running")

        # if no browser connection can be found: open browser
        if not ARGS.no_browser and number_of_connected_jsclients() == 0:
            open_browser()
            wait_for_connected_jsclient()

        # if a filename was given and something was piped into smdv, throw error:
        if ARGS.filename and not os.isatty(0):
            warnings.warn(
                "when piping into smdv while supplying a "
                "filename, the filename takes precedence."
            )

        # if filename argument was given, sync filename to smdv
        if ARGS.filename:
            update_filename()
            return 0

        # else, check if something was piped into smdv and update the body accordingly:
        if not os.isatty(0):
            send_message_from_stdin()
            return 0

        # only happens when no arguments are supplied, nor anything was piped into smdv:
        return 0

    except Exception as e:
        print(e, file=sys.stderr)
        return 1


def md2body(content: str = "") -> str:
    """ convert markdown to html using the github flavored markdown [gfm] spec of pandoc

    Args:
        content: the markdown string to convert

    Returns:
        html: str: the resulting html

    """

    html = MD_INTERPRETER.convert(content)

    urls = (re.findall('src="(.*?)"', html)
            + re.findall("src='(.*?)'", html)
            + re.findall('href="(.*?)"', html)
            + re.findall("href='(.*?)'", html))


    cwd = os.path.abspath(os.getcwd()).replace(ARGS.home, "") + "/"
    for url in urls:
        if not (url.startswith("/") or url.startswith("http://") or url.startswith("https://")):
            html = html.replace(url, f"http://{ARGS.host}:{ARGS.port}/@static{cwd}{url}")

    return html


# open a new browser
def open_browser():
    """ spawn a new browser to open smdv

    Args:
        filename: str="": the filename to open the browser at.
    """
    url = f"http://{ARGS.host}:{ARGS.port}"
    if ARGS.browser == "chromium --app":
        subprocess.Popen(["chromium", f"--app={url}"])
    elif ARGS.browser:
        subprocess.Popen([ARGS.browser, url])
    elif subprocess.call(["which", "xdg-open"]) == 0:
        subprocess.Popen(["xdg-open", url])
    else:
        webbrowser.open(url)


# parse command line arguments
def parse_args(args: tuple, **kwargs) -> argparse.Namespace:
    """ populate the smdv command line arguments

    Args:
        args: the arguments to parse
        **kwargs: override the default arguments

    Returns:
        parsed_args: the parsed arguments

    """
    ## Argument parser
    parser = argparse.ArgumentParser(description="smdv: a Simple MarkDown Viewer")
    parser.add_argument(
        "filename",
        type=str,
        nargs="?",
        default=kwargs.get("filename", ""),
        help="path or file to open with smdv",
    )
    parser.add_argument(
        "-H",
        "--home",
        default=kwargs.get("home", os.path.expanduser("~")),
        help="set the root folder of the smdv server",
    )
    parser.add_argument(
        "--stdin",
        nargs="?",
        default=kwargs.get("stdin", "md"),
        choices=["md", "html", "txt"],
        help=(
            "read content for smdv from stdin. Takes optional encoding types:"
            "    md (default), html"
        ),
    )
    parser.add_argument(
        "-p",
        "--port",
        default=kwargs.get("port", "9876"),
        help="port on which smdv is served.",
    )
    parser.add_argument(
        "-w",
        "--websocket-port",
        default=kwargs.get("websocket_port", "9877"),
        help="port for websocket communication",
    )
    parser.add_argument(
        "--host",
        default=kwargs.get("host", "localhost"),
        help="host on which smdv is served (for now, only localhost is supported)",
        choices=["localhost", "127.0.0.1"],
    )
    parser.add_argument(
        "--websocket-host",
        default=kwargs.get("websocket_host", "localhost"),
        help="host for websocket communication (for now, only localhost is supported)",
        choices=["localhost", "127.0.0.1"],
    )
    parser.add_argument(
        "--md-css-cdn",
        default=kwargs.get(
            "md_css_cdn",
            "https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/3.0.1/github-markdown.css",
        ),
        help="location of [github flavored] markdown css cdn (can be a local file)",
    )
    parser.add_argument(
        "-b",
        "--browser",
        default=kwargs.get("browser", os.environ.get("BROWSER", "")),
        help="default browser to spawn (uses $BROWSER by default)",
    )
    parser.add_argument(
        "-r",
        "--restart",
        action="store_true",
        default=kwargs.get("restart", False),
        help="force a restart of smdv (both servers)",
    )
    parser.add_argument(
        "--hide-navbar",
        action="store_true",
        default=kwargs.get("hide_navbar", False),
        help="don't show the smdv navbar by default",
    )
    parser.add_argument(
        "-t",
        "--terminal",
        default=kwargs.get("terminal", os.environ.get("TERMINAL", "")),
        help="default terminal to spawn (uses $TERMINAL by default)",
    )
    parser.add_argument(
        "-B",
        "--no-browser",
        action="store_true",
        default=kwargs.get("no_browser", False),
        help="start the server without opening a browser.",
    )
    parser.add_argument(
        "-v",
        "--nvim-address",
        default=kwargs.get("nvim_address", "127.0.0.1:9878"),
        help="address or socket to communicate with vim",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        default=kwargs.get("interactive", False),
        help=("open smdv in interactive mode (every file opened in "
              "smdv will also automatically be opened in vim)."),
    )
    single_shot_arguments = parser.add_mutually_exclusive_group()
    single_shot_arguments.add_argument(
        "--server-status",
        action="store_true",
        default=kwargs.get("server_status", False),
        help="ask status of the smdv server",
    )
    single_shot_arguments.add_argument(
        "--websocket-server-status",
        action="store_true",
        default=kwargs.get("websocket_server_status", False),
        help="ask status of the smdv server",
    )
    single_shot_arguments.add_argument(
        "--start-server",
        action="store_true",
        default=kwargs.get("start_server", False),
        help="start the smdv server (without doing anything else)",
    )
    single_shot_arguments.add_argument(
        "--stop-server",
        action="store_true",
        default=kwargs.get("stop_server", False),
        help="stop the smdv server (without doing anything else)",
    )
    single_shot_arguments.add_argument(
        "--start-websocket-server",
        action="store_true",
        default=kwargs.get("start_websocket_server", False),
        help="start the smdv websocket server (without doing anything else)",
    )
    single_shot_arguments.add_argument(
        "--stop-websocket-server",
        action="store_true",
        default=kwargs.get("stop_websocket_server", False),
        help="stop the smdv websocket server (without doing anything else)",
    )
    single_shot_arguments.add_argument(
        "--stop",
        action="store_true",
        default=kwargs.get("stop", False),
        help="stop smdv running in the background (kills both servers)",
    )
    single_shot_arguments.add_argument(
        "--start",
        action="store_true",
        default=kwargs.get("start", False),
        help="start smdv (both servers)",
    )
    parsed_args = parser.parse_args(args=args)
    if parsed_args.stdin is None:
        parsed_args.stdin = "md"
    if parsed_args.home.endswith("/"):
        parsed_args.home = parsed_args.home[:-1]
    if not os.path.isdir(parsed_args.home):
        raise ValueError(f"invalid home location given from smdv: {parsed_args.home}")
    if parsed_args.hide_navbar:
        raise ValueError(f"hiding the navbar is not yet supported")
    return parsed_args


# print a message (useful for logging)
def print_message(message: dict, **kwargs):
    """ print a message

    Args:
        message: the message to print nicely
        **kwargs: the keyword arguments to print/suppress (defaults to all true)
    """
    indent = kwargs.pop("indent", 0)
    for k, v in message.items():
        if kwargs.get(k, True):
            if k == "fileBody" or k == "cwdBody":
                v = v[:20]
            print(f"{'    '*indent}{k}\t{repr(v)}")


# get status for the smdv server
def request_server_status(server: str = "flask") -> str:
    """ request the smdv server status

    Args:
        server: the server to ask the status for ["flask", "websocket"]

    Returns:
        status: str: the smdv server status
    """
    if server == "websocket":
        connection = http.client.HTTPConnection(
            ARGS.websocket_host, ARGS.websocket_port
        )
    elif server == "flask":
        connection = http.client.HTTPConnection(ARGS.host, ARGS.port)
    else:
        raise ValueError(
            "request_server_status expects a server value of 'flask' or 'server'"
        )
    try:
        connection.connect()
        server_status = "running"
    except ConnectionRefusedError:
        server_status = "stopped"
    finally:
        connection.close()
    return server_status


# run the flask server
def run_flask_server():
    """ start the flask server """
    create_app().run(debug=False, port=ARGS.port, host=ARGS.host, threaded=True)


# run server in new subprocess
def run_server_in_subprocess(server="flask"):
    """ start the websocket server in a subprocess

    Args:
        server: which server to run in subprocess ["flask", "websocket"]
    """
    args = {
        "--home": ARGS.home,
        "--stdin": ARGS.stdin,
        "--port": ARGS.port,
        "--websocket-port": ARGS.websocket_port,
        "--host": ARGS.host,
        "--websocket-host": ARGS.websocket_host,
        "--md-css-cdn": ARGS.md_css_cdn,
        "--nvim-address": ARGS.nvim_address,
    }

    args_list = [str(s) for kv in args.items() for s in kv]  # flattened dict as list
    if ARGS.interactive:
        args_list += ["--interactive"]
    if server == "flask":
        args_list += ["--start-server"]
    elif server == "websocket":
        args_list += ["--start-websocket-server"]
    else:
        raise ValueError(
            "server to start in subprocess should be either 'flask' or 'websocket'"
        )
    with open(os.devnull, "w") as null:
        subprocess.Popen(["smdv"] + args_list, stdout=null, stderr=null)


# websocket server
def run_websocket_server():
    """ start and run the websocket server """
    global WEBSOCKETS_SERVER
    WEBSOCKETS_SERVER = websockets.serve(
        serve_client, ARGS.websocket_host, ARGS.websocket_port
    )
    EVENT_LOOP.run_until_complete(WEBSOCKETS_SERVER)
    EVENT_LOOP.run_forever()


# send a message to the websocket server at the python client
def send_as_pyclient(message: dict):
    """ send a message to the websocket server as the python client

    Args:
        message: the message to send (in dictionary format)
    """
    try:
        EVENT_LOOP.run_until_complete(send_as_pyclient_async(message))
    except RuntimeError:
        pass  # allows messages to be lost when sending many messages at once.


# stop the smdv server
def send_delete_request_to_server():
    """ stop the smdv server by sending a DELETE request

    Returns:
        exit_status: the exit status (0=success, 1=failure)
    """
    connection = http.client.HTTPConnection(ARGS.host, ARGS.port)
    try:
        connection.connect()
        connection.request("DELETE", "/")
        response = connection.getresponse().read().decode().strip()
        exit_code = 0 if response == "success." else 1
    except Exception as e:
        print(e)
        exit_code = 1
    finally:
        connection.close()
        return exit_code


# update body of smdv from stdin
def send_message_from_stdin():
    """ read content from stdin and place it in the html body """
    content = sys.stdin.read()
    try:
        message = json.loads(content)
    except json.decoder.JSONDecodeError:
        message = {"fileBody": content}
    cwd = os.path.abspath(os.path.expanduser(os.getcwd()))[len(ARGS.home) :] + "/"
    message["func"] = message.get("func", "file")
    message["cwd"] = message.get("cwd", cwd)
    message["cwdEncoded"] = bool(message.get("cwdEncoded", True))
    message["cwdBody"] = message.get("cwdBody", dir2body(cwd))
    message["cwdCwd"] = message.get("fileCwd", cwd)
    message["filename"] = message.get("filename", "@pipe")
    message["fileEncoding"] = message.get("fileEncoding", ARGS.stdin)
    message["fileEncoded"] = bool(message.get("fileEncoded", False))
    message["fileOpen"] = bool(message.get("fileOpen", True))
    message["nvimAddress"] = ARGS.nvim_address
    send_as_pyclient(message)


# check if a socket is in use
def socket_in_use(address: str) -> bool:
    """ check if a socket is in use

    Args:
        address: str: the address of the unix/inet socket

    Returns:
        in_use: bool: wether the socket is in use or not.
    """

    if ":" in address:  # inet socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host, port = address.split(":")
        result = sock.connect_ex((host, int(port)))
        if result == 0:
            return True
        else:
            return False
        sock.close()
    else:  # unix socket
        if os.path.exists(address):
            return True
        return False


# convert text file to html
def txt2body(content: str) -> str:
    """ Convert text content to html

    Args:
        content: the content to encode as html
    """
    content = f"```\n{content}\n```"
    return md2body(content)


# send message to smdv to load filename
def update_filename():
    """ open filename in smdv """
    path = os.path.abspath(os.path.expanduser(ARGS.filename))
    if path.startswith(ARGS.home):
        path = path[len(ARGS.home) :]
    cwd, filename = change_current_working_directory(path)
    with open(filename, "r") as file:
        content = file.read()
    message = {
        "func": "file",
        "cwd": cwd,
        "cwdBody": dir2body(cwd),
        "cwdEncoded": True,
        "filename": filename,
        "fileBody": content,
        "fileCwd": cwd,
        "fileOpen": True,
        "fileEncoding": "",
        "fileEncoded": False,
        "NvimAddress": ARGS.nvim_address,
    }
    send_as_pyclient(message)


def validate_message(message: str):
    """ check if the message is a valid websocket message """
    if message.get("client", "func") in {"dir", "file"}:
        keys = {
            "client",
            "func",
            "cwd",
            "cwdBody",
            "cwdEncoded",
            "filename",
            "fileBody",
            "fileCwd",
            "fileOpen",
            "fileEncoding",
            "fileEncoded",
        }
        for key in keys:
            assert key in message, f"message {message} has no key '{key}'"
            assert key in keys, f"{key} is not a valid message key"


# wait until at least on js client is online.
def wait_for_connected_jsclient(interval: float = 0.3, max_attempts: int = 6):
    """ wait until a connection to the browser can be made.

    Args:
        interval: the interval time to check for the websocket server connection
        max_attempts: the maximum number of tries before exiting with failure

    Returns:
        exit_status: the exit status after waiting
    """
    for _ in range(max_attempts):  # max 10 tries, throw error otherwise
        if number_of_connected_jsclients() > 0:
            return
        time.sleep(interval)
    raise ConnectionRefusedError("could not establish a connection with a browser")


# block until a connection to the websocket server can be established
def wait_for_server(
    interval: float = 0.3,
    max_attempts: int = 10,
    server: str = "flask",
    status: str = "running",
):
    """ wait until a connection to one of the servers can be established

    Args:
        interval: the interval time to check for the websocket server connection
        max_attempts: the maximum number of tries before exiting with failure
        server: the server to ask the status for ["flask", "websocket"]
        status: wait for ["running", "stopped"] status.

    Returns:
        exit_status: the exit status after waiting
    """
    if status not in ["running", "stopped"]:
        raise ValueError("wait for server expects status 'running' or 'stopped'")
    for _ in range(max_attempts):  # max 10 tries, throw error otherwise
        if request_server_status(server=server) == "running":
            return
        time.sleep(interval)
    raise ConnectionRefusedError(
        f"connection to {server} server could not be established"
    )


if __name__ == "__main__":
    exit(main())
