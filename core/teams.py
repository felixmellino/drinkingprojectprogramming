"""Team settings and display identities. Persistence enforces joins atomically."""

ERRORS = {
    "team_full": "That team is full. Choose another team with a free place; departed members keep their reserved places.",
    "lobby_full": "This lobby is full, including reserved places for departed members. Join or create another lobby.",
    "team_locked": "Your team is locked after your first scored check-in. Continue with your current team or choose a different team in a new lobby.",
    "random_team_locked": "Teams are assigned at random in this lobby. Continue with your assigned team; create a lobby with Players choose to select teams manually.",
    "lobby_finished": "This lobby has finished and its teams are frozen. Create or join a new lobby to play again.",
    "invalid_team": "This team is not in the selected lobby. Reopen the lobby and choose one of its teams.",
    "invalid_team_name": "Use a team name of 1–40 characters.",
    "permission_denied": "This team action is not allowed for your membership. Reopen the lobby and use your own team's edit controls.",
    "team_settings_frozen": "An existing lobby's team settings cannot be changed. Create a new lobby to use a different team configuration.",
    "membership_identity_frozen": "This membership cannot be moved to another player or lobby. Join the intended lobby with its invite code instead.",
}


def validate_config(mode, count, capacity, assignment):
    if mode == "individual":
        if any(value is not None for value in (count, capacity, assignment)):
            raise ValueError("Individual lobbies cannot have team settings.")
    elif mode == "team":
        if type(count) is not int or not 2 <= count <= 16:
            raise ValueError("Choose between 2 and 16 teams.")
        if type(capacity) is not int or not 1 <= capacity <= 20:
            raise ValueError("Choose between 1 and 20 players per team.")
        if assignment not in ("random", "manual"):
            raise ValueError("Choose random assignment or player choice.")
    else:
        raise ValueError("Choose individual or team mode.")


def team_name(value):
    value = value.strip()
    if not 1 <= len(value) <= 40 or any(ord(char) < 32 for char in value):
        raise ValueError("Use a team name of 1–40 characters without control characters.")
    return value


def competitor(entry):
    """An accepted entry keeps its team identity even if membership changes later."""
    return entry.team_id or entry.membership_id
