# Prerequisites

Before you can run this project, you need the following tools installed on your machine.

## Required Tools

- A GitHub account
- A terminal-based git client or a GUI Git client such as [GitHub Desktop](https://desktop.github.com/) or the Git plugin for VSCode
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — the app, API, and database all run in containers
- [VSCode](https://code.visualstudio.com/) with the Python extension installed
  - You may use another Python/code editor, but course staff will only support VS Code

## Python Environment Setup

You need a local Python 3.11 environment so your IDE can provide autocompletion, linting, and error highlighting as you write code. The app itself always runs inside the Docker containers — the local install is purely for editor support.

Choose **one** of the two options below.

---

### Option A: Anaconda / Miniconda

If you do not already have Anaconda or Miniconda installed, download and install one of them first:

- [Anaconda](https://www.anaconda.com/download) — full distribution, includes many scientific packages
- [Miniconda](https://www.anaconda.com/docs/getting-started/miniconda/install) — minimal installer, downloads packages on demand

**1. Create a new conda environment named `db-proj` using Python 3.11:**

```bash
conda create -n db-proj python=3.11
```

**2. Activate the environment:**

```bash
conda activate db-proj
```

**3. Install the project dependencies:**

```bash
cd api
pip install -r requirements.txt
cd ../app/src
pip install -r requirements.txt
```

> `..` means go up one directory level (back to the project root) before entering `app/src`.

**4. Select the interpreter in VSCode:**

Open the Command Palette (`Cmd+Shift+P` on Mac, `Ctrl+Shift+P` on Windows/Linux), type **Python: Select Interpreter**, and choose the `db-proj` conda environment.

---

### Option B: venv (Python Standard Library)

This option uses the `venv` module that ships with Python. You must already have Python 3.11 installed. You can download it from [python.org](https://www.python.org/downloads/).

**1. Create a virtual environment in the project root:**

```bash
python3.11 -m venv .venv
```

**2. Activate the environment:**

| Platform | Command |
|----------|---------|
| macOS / Linux | `source .venv/bin/activate` |
| Windows (cmd) | `.venv\Scripts\activate.bat` |
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |

Your shell prompt will change to show `(.venv)` when the environment is active.

**3. Install the project dependencies:**

```bash
cd api
pip install -r requirements.txt
cd ../app/src
pip install -r requirements.txt
```

**4. Select the interpreter in VSCode:**

Open the Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`), type **Python: Select Interpreter**, and choose the `.venv` entry that points to this project folder.

---

## Verifying Your Setup

After completing either option, confirm the right Python is active:

```bash
python --version   # should show Python 3.11.x
pip list           # should include flask, streamlit, and other project packages
```

Confirm Docker is running:

```bash
docker --version
docker compose version
```
