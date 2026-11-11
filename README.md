# ArenaLink

> Bring Arena.ai project files onto your PC, with local review before every operation.

![Version](https://img.shields.io/badge/version-0.1.0-7650c9?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square)

ArenaLink pairs a desktop app with a browser extension. Ask Arena.ai for an action plan, select the JSON response, and send it to your desktop. Review the full plan before approving it. Copy the results back into the conversation when you want the model to continue.

**This prototype is a manual bridge, not a native Arena.ai tool integration.** It does not use an Arena API or give models autonomous computer control. No Arena.ai affiliation is implied.

## Features

| Operation | Behavior |
| --- | --- |
| `mkdir` | Create folders, including parent directories |
| `write` | Save UTF-8 files; existing files require `overwrite: true` |
| `read` | Read a UTF-8 file, up to 500 KB |
| `list` | List a folder, up to 500 entries |

The app listens on loopback only (`127.0.0.1:47831`). Each launch generates a new pairing token. All requests, including reads, require desktop approval. Paths must stay inside the selected workspace. Detected symlinks and junctions are rejected. Terminal commands, deletion, and general desktop control are not included.

## Start on Windows

1. Install **Python 3.11 or newer** from [python.org](https://www.python.org/downloads/). Include Tcl/Tk and the Python launcher.
2. Download this repository using **Code → Download ZIP**, then extract it.
3. Double-click **Start-ArenaLink.bat**.
4. Click **Choose workspace** and select the project folder to work in.
5. Click **Copy pairing token**.

No Python packages are required to run the application. You can also launch it with:

```sh
python app.py
```

## Load the extension

1. Open `chrome://extensions`, `brave://extensions`, or `edge://extensions`.
2. Enable **Developer mode** and choose **Load unpacked**.
3. Select this repository's **extension** folder.
4. Pin ArenaLink, open its popup, and paste the pairing token.

The extension targets Chromium browsers. Windows packaging and live browser pairing still need verification on a Windows machine.

## Use with Arena.ai

1. Paste [ARENA_PROMPT.txt](ARENA_PROMPT.txt) into an Arena.ai conversation.
2. Tell the model what you want to create.
3. Select the complete JSON plan in its response.
4. Open ArenaLink and click **Use selected Arena.ai text**, or paste the JSON directly into the popup.
5. Click **Send for approval** and keep the popup open.
6. Review paths and content in the desktop app. Click **Approve and run** or **Reject**.
7. Click **Copy result** and paste it into Arena.ai for the next step.

Example:

```json
{
  "actions": [
    {"op": "mkdir", "path": "portfolio"},
    {
      "op": "write",
      "path": "portfolio/index.html",
      "content": "<!doctype html><html><body><h1>Hello from ArenaLink</h1></body></html>"
    }
  ]
}
```

<details>
<summary><strong>Approval behavior and limits</strong></summary>

- Requests expire after two minutes. Only one request can be pending at a time.
- Plans allow up to 30 actions; requests are limited to 1 MB.
- The desktop preview shows the received plan. Editing the preview does not change the actions.
- A batch stops on its first failure. Earlier successful actions remain applied; batches are not transactions.
- If the popup closes or loses connection, inspect desktop activity before retrying. Approved operations may already have completed.
- Tokens use browser session storage. Restarting the desktop app requires pairing again.
- Use a project folder you control. This prototype is not a security boundary against local processes changing that folder while actions run.

</details>

## Build a Windows executable

With Python installed on Windows, double-click **Build-Windows.bat**. It installs PyInstaller from PyPI and builds `dist/ArenaLink.exe`. The executable is unsigned. A Windows binary is not included and has not been built or tested here.

## Development

```sh
python -m unittest discover -s tests -v
```

Tests cover file operations, workspace confinement, overwrites, batch failures, authentication, and HTTP approval. The desktop UI uses Tkinter; Linux may require the distribution's `python3-tk` package.

## Roadmap

- [x] Local desktop companion and pairing token
- [x] Workspace file operations with approval
- [x] Extension for selected action plans and results
- [ ] Verify Windows UI, executable packaging, and live browser pairing
- [ ] Add file diffs and backups before overwrites
- [ ] Investigate supported, automatic Arena.ai tool integration
