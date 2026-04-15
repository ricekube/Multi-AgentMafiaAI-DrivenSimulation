import requests
import random
import time
import re

OLLAMA_URL = "http://localhost:11434/api/chat"

# ---------------------------
# CONFIG
# ---------------------------

PLAYERS = [
    {"name": "Red", "model": "gpt-oss:120b-cloud"},
    {"name": "Blue", "model": "gpt-oss:120b-cloud"},
    {"name": "Green", "model": "gpt-oss:120b-cloud"},
    {"name": "Yellow", "model": "gpt-oss:120b-cloud"},
    {"name": "Purple", "model": "gpt-oss:120b-cloud"},
    {"name": "Teal", "model": "gpt-oss:120b-cloud"},
]

MAFIA_COUNT = 1
MAX_ROUNDS = 10

# Rake tracker - tracks kills and eliminations
RAKE = {
    "night_kills": 0,
    "day_lynches": 0,
    "total_casualties": 0
}

TOKEN_MULTIPLIER = {
    "gemini-3-flash-preview": 6,
    "gemini-2.0-flash": 6,
    "gemini-2.5-flash": 6,
}


# ---------------------------
# OLLAMA CALL (FIXED)
# ---------------------------
def warmup(model):
    try:
        requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False
            },
            timeout=300
        )
    except:
        pass


def ask_model(model, messages, max_tokens=200):
    """
    Call Ollama with better error handling and fallback responses.
    """
    patched = [dict(m) for m in messages]
    adjusted_tokens = max_tokens * TOKEN_MULTIPLIER.get(model, 1)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "messages": patched,
                "stream": False,
                "options": {
                    "temperature": 0.9,
                    "num_predict": adjusted_tokens,
                },
            },
            timeout=300,
        )

        # Check HTTP status
        if response.status_code != 200:
            print(f"  ⚠️  HTTP {response.status_code} for {model}")
            return "[Model returned error]"

        data = response.json()

        # Check for Ollama errors
        if "error" in data:
            print(f"  ⚠️  {data['error']}")
            return "[Model error - check if model is loaded]"

        if "message" not in data or "content" not in data["message"]:
            print(f"  ⚠️  Unexpected response: {list(data.keys())}")
            return "[Invalid response format]"

        content = data["message"]["content"].strip()

        # Strip thinking tags
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        # If empty after stripping, return fallback
        if not content:
            print(f"  ⚠️  Empty response from {model}")
            return "[Model produced no output]"

        return content

    except requests.exceptions.Timeout:
        print(f"  ⚠️  Request timed out for {model}")
        return "[Timed out - model may be slow or stuck]"
    except requests.exceptions.ConnectionError:
        print(f"  ⚠️  Cannot connect to Ollama at {OLLAMA_URL}")
        return "[Connection failed - is Ollama running?]"
    except Exception as e:
        print(f"  ⚠️  Unexpected error: {type(e).__name__}: {e}")
        return f"[Error: {type(e).__name__}]"


# ---------------------------
# GAME LOGIC
# ---------------------------

def assign_roles(players):
    mafia = random.sample(players, MAFIA_COUNT)
    for p in players:
        p["role"] = "Mafia" if p in mafia else "Villager"
        p["alive"] = True


def get_alive(players):
    return [p for p in players if p["alive"]]


def mafia_alive(players):
    return [p for p in players if p["alive"] and p["role"] == "Mafia"]


def villagers_alive(players):
    return [p for p in players if p["alive"] and p["role"] == "Villager"]


def check_win(players):
    mafia = mafia_alive(players)
    villagers = villagers_alive(players)

    if not mafia:
        return "Villagers"
    if len(mafia) >= len(villagers):
        return "Mafia"
    return None


# ---------------------------
# NIGHT PHASE
# ---------------------------

def night_phase(players):
    print("\n🌙 --- NIGHT PHASE ---")

    mafia_players = mafia_alive(players)
    alive = get_alive(players)

    if not mafia_players:
        return

    mafia = mafia_players[0]

    targets = [p for p in alive if p != mafia]
    target_names = [p["name"] for p in targets]

    prompt = f"""You are playing Mafia. You are the secret Mafia member.
Alive players (potential targets): {", ".join(target_names)}

First, briefly explain your reasoning for who to eliminate (1-2 sentences).
Then on the LAST LINE write: TARGET: <name>

Only choose from the list above."""

    print(f"\n🔪 {mafia['name']} (Mafia) is deciding who to kill...")

    raw_response = ask_model(
        mafia["model"],
        [{"role": "user", "content": prompt}],
        max_tokens=180,
    )

    # Show the mafia's full thinking (even if it's an error)
    if raw_response.startswith("["):
        print(f"💭 {mafia['name']}: *{raw_response}*")
        print(f"   (Making random choice due to model error)")
    else:
        print(f"💭 {mafia['name']}'s reasoning:\n{raw_response}\n")

    # Parse TARGET: <name> line first
    victim = None
    target_match = re.search(r"TARGET:\s*(\w+)", raw_response, re.IGNORECASE)
    if target_match:
        candidate = target_match.group(1)
        for p in targets:
            if p["name"].lower() == candidate.lower():
                victim = p
                break

    # Fallback: scan anywhere in the response for a player name
    if not victim:
        for p in targets:
            if p["name"].lower() in raw_response.lower():
                victim = p
                break

    # Final fallback: random choice
    if not victim:
        victim = random.choice(targets)
        print(f"   (Choosing randomly due to unclear response)")

    victim["alive"] = False
    RAKE["night_kills"] += 1
    RAKE["total_casualties"] += 1
    print(f"💀 {victim['name']} was killed during the night.")
    print(
        f"📊 RAKE: {RAKE['night_kills']} night kills, {RAKE['day_lynches']} lynches, {RAKE['total_casualties']} total casualties")


# ---------------------------
# DAY DISCUSSION
# ---------------------------

def discussion_phase(players):
    print("\n☀️ --- DAY DISCUSSION ---")

    alive = get_alive(players)
    names = [p["name"] for p in alive]

    for player in alive:
        prompt = f"""You are {player['name']}, a player in a Mafia game. You are a {player['role']}.
The players still alive are: {", ".join(names)}.

It is the day discussion phase. Speak out loud to the group — share your suspicions, defend yourself, \
or react to what others have said. Be natural and conversational, like you're actually talking to people. \
Keep it to 2-4 sentences. Do NOT break character or mention being an AI."""

        print(f"\n🗣 {player['name']} ({player['model']}) speaking...")

        reply = ask_model(
            player["model"],
            [{"role": "user", "content": prompt}],
            max_tokens=200,
        )

        # Handle both error and normal responses
        if reply.startswith("["):
            print(f"   💬 {player['name']}: *stays silent* ({reply})")
        else:
            print(f"   💬 {player['name']}: \"{reply}\"")

        time.sleep(1)


# ---------------------------
# VOTING PHASE
# ---------------------------

def voting_phase(players):
    print("\n🗳 --- VOTING PHASE ---")

    alive = get_alive(players)
    names = [p["name"] for p in alive]

    votes = {}

    for player in alive:
        others = [p["name"] for p in alive if p != player]

        prompt = f"""You are {player['name']} in a Mafia game. You are a {player['role']}.
Alive players: {", ".join(names)}

Give 1-2 sentences explaining who you suspect and why, then on the LAST LINE write:
VOTE: <name>

Only vote for someone from the list above."""

        vote_response = ask_model(
            player["model"],
            [{"role": "user", "content": prompt}],
            max_tokens=120,
        )

        # Show their reasoning
        if vote_response.startswith("["):
            print(f"\n{player['name']}: *stays silent* ({vote_response})")
        else:
            print(f"\n{player['name']}: \"{vote_response}\"")

        # Parse VOTE: <name> line first
        chosen = None
        vote_match = re.search(r"VOTE:\s*(\w+)", vote_response, re.IGNORECASE)
        if vote_match:
            candidate = vote_match.group(1)
            for name in others:
                if name.lower() == candidate.lower():
                    chosen = name
                    break

        # Fallback: scan anywhere in response for a player name
        if not chosen:
            for name in others:
                if name.lower() in vote_response.lower():
                    chosen = name
                    break

        # Final fallback: random vote
        if not chosen:
            chosen = random.choice(others)
            print(f"  (Random vote due to unclear response)")

        votes[chosen] = votes.get(chosen, 0) + 1
        print(f"  ✋ {player['name']} votes for {chosen}")
        time.sleep(0.5)

    # Find highest votes
    eliminated = max(votes, key=votes.get)

    for p in alive:
        if p["name"] == eliminated:
            p["alive"] = False
            RAKE["day_lynches"] += 1
            RAKE["total_casualties"] += 1
            print(f"\n🔥 {p['name']} was lynched! (Votes: {votes[eliminated]})")
            print(f"   They were a {p['role']}!")
            print(
                f"📊 RAKE: {RAKE['night_kills']} night kills, {RAKE['day_lynches']} lynches, {RAKE['total_casualties']} total casualties")
            break


# ---------------------------
# MAIN GAME LOOP
# ---------------------------

def main():
    print("🎭 --- MULTI-MODEL MAFIA --- 🎭")
    print(f"Players: {len(PLAYERS)} | Mafia: {MAFIA_COUNT}")
    print(f"Max Rounds: {MAX_ROUNDS}")
    print("=" * 50)

    players = PLAYERS.copy()

    assign_roles(players)

    round_num = 1

    while round_num <= MAX_ROUNDS:
        print(f"\n{'=' * 50}")
        print(f"ROUND {round_num}")
        print(f"{'=' * 50}")

        night_phase(players)

        winner = check_win(players)
        if winner:
            break

        discussion_phase(players)
        voting_phase(players)

        winner = check_win(players)
        if winner:
            break

        round_num += 1

    print("\n🏆 ========== GAME OVER ========== 🏆")
    if winner:
        print(f"Winner: {winner}!")
    else:
        print("No winner (max rounds reached).")

    print(f"\n📊 FINAL RAKE STATS:")
    print(f"   Night kills: {RAKE['night_kills']}")
    print(f"   Day lynches: {RAKE['day_lynches']}")
    print(f"   Total casualties: {RAKE['total_casualties']}")
    print("=" * 50)


if __name__ == "__main__":
    main()