
<p align="center">
  <img src="https://constellab.space/assets/fl-logo/constellab-logo-text-white.svg" alt="Constellab Logo" width="80%">
</p>

<br/>

# 👋 Welcome to GWS AI Toolkit 

```gws_ai_toolkit``` is a [Constellab](https://constellab.io) library (called bricks) developped by [Gencovery](https://gencovery.com/). GWS stands for Gencovery Web Services.

## 🚀 What is Constellab?


✨ [Gencovery](https://gencovery.com/) is a software company that offers [Constellab](https://constellab.io)., the leading open and secure digital infrastructure designed to consolidate data and unlock its full potential in the life sciences industry. Gencovery's mission is to provide universal access to data to enhance people's health and well-being.

🌍 With our Fair Open Access offer, you can use Constellab for free. [Sign up here](https://constellab.space/). Find more information about the Open Access offer here (link to be defined).


## ✅ Features

Provides tools for AI-driven data analysis and visualization in the life sciences.
Contains RAG tools : 
- Dify
- Ragflow

Other AI tools:
- Table copilot
- Knowledge-base chat with Document Focus — scope a conversation to one or a few documents, either
  via an in-chat picker or by starting a focused chat from a document's row on the knowledge-base
  page.

> **Retired capability (August 2026)** — the standalone AI Expert mode (chat about a single document
> outside a chat profile) is gone; Document Focus on knowledge-base chat covers the same need.
> Existing AI Expert conversations remain visible, read-only, in history.
> See `docs/adr/0002-retire-ai-expert-fold-into-document-focus.md`.

## 📄 Documentation

💫 For Constellab application documentation, click [here](https://constellab.community/bricks/gws_academy/latest/doc/getting-started/b38e4929-2e4f-469c-b47b-f9921a3d4c74)

## 🛠️ Installation

The `gws_ai_toolkit` brick requires the `gws_core` brick.

### 🔥 Recommended Method

The best way to install a brick is through the Constellab platform. With our Fair Open Access offer, you get a free cloud data lab where you can install bricks directly. [Sign up here](https://constellab.space/)

Learn about the data lab here : [Overview](https://constellab.community/bricks/gws_academy/latest/doc/digital-lab/overview/294e86b4-ce9a-4c56-b34e-61c9a9a8260d) and [Data lab management](https://constellab.community/bricks/gws_academy/latest/doc/digital-lab/on-cloud-digital-lab-management/4ab03b1f-a96d-4d7a-a733-ad1edf4fb53c)

### 🔧 Manual installation

This section is for users who want to install the brick manually. It can also be used to install the brick manually in the Constellab Codelab.

We recommend installing using Ubuntu 22.04 with python 3.10.

#### Usage


▶️ To start the server :

```bash
gws server run
```

🕵️ To run a given unit test

```bash
gws server test [TEST_FILE_NAME]
```

Replace `[TEST_FILE_NAME]` with the name of the test file (without `.py`) in the tests folder. Execute this command in the folder of the brick.

🕵️ To run the whole test suite, use the following command:

```bash
gws server test all
```

**RagFlow Tests**: Some tests (e.g., `test_ragflow_service`) require RagFlow credentials. Create a `.env.test` file in the brick root with:
```bash
RAGFLOW_API_KEY=your-api-key
RAGFLOW_BASE_URL=http://localhost:9380
RAGFLOW_DATASET_ID=your-dataset-id
RAGFLOW_CHAT_ID=your-chat-id
```

📌 VSCode users can use the predefined run configuration in `.vscode/launch.json`.

## 🤗 Community

🌍 Join the Constellab community [here](https://constellab.community/) to share and explore stories, code snippets and bricks with other users.

🚩 Feel free to open an issue if you have any question or suggestion.

☎️ If you have any questions or suggestions, please feel free to contact us through our website: [Constellab](https://constellab.io/).

## 🌎 License

```gws_ai_toolkit``` is completely free and open-source and licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html).

<br/>


This brick is maintained with ❤️ by [Gencovery](https://gencovery.com/).

<p align="center">
  <img src="https://framerusercontent.com/images/Z4C5QHyqu5dmwnH32UEV2DoAEEo.png?scale-down-to=512" alt="Gencovery Logo"  width="30%">
</p>