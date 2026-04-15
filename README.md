Work in progress

Multi-Model Mafia (Local LLM Simulation)

This project is a fully automated AI vs AI Mafia game simulation, where multiple language models take on roles (Mafia and Villagers), discuss, accuse, vote, and eliminate each other until a winner is determined.

Each player is powered by a different local language model, creating diverse reasoning styles, personalities, and emergent gameplay.

🧠 How It Works
Players are assigned roles (Mafia or Villager)
Night Phase: Mafia selects a player to eliminate
Day Phase: All players discuss and accuse each other
Voting Phase: Players vote to eliminate a suspect
The game continues until:
Mafia equals or outnumbers villagers → Mafia wins
All Mafia are eliminated → Villagers win
⚙️ Requirements

⚠️ This project requires a local LLM runtime to function.

It is designed to run using Ollama.

Setup:
Install Ollama

Pull required models:

ollama pull gpt-oss:120b-cloud

Start the server:

ollama serve

Run the game:

python mafia_multimodel.py
🚀 Features
Multi-model AI interaction system
Fully automated Mafia game loop
Dynamic discussion and voting phases
No API keys required
Runs entirely locally
Easily extendable with new roles and models

Running locally to avoid API costs


