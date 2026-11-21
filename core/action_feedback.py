"""Shared reasons and recovery steps. These describe rules, never change them."""
from core.constants import MAX_GPS_ACCURACY_M, MAX_GPS_AGE_SECONDS
from core.scoring_v1 import format_points
from core.scoring_v1 import current_time, next_opening, utc
from zoneinfo import ZoneInfo


LOCATION_MESSAGES = {
    "off": "Location tracking is off. Open Profile → Location and turn it on, then return here.",
    "denied": "Location access is blocked. Allow location for this site in your browser settings and turn on your phone's location services. Then open Profile → Location and turn it on.",
    "waiting": "Your location has not been found yet. Allow access if asked and keep this page open. If it keeps searching, open Profile → Location and turn it on again.",
    "stale": f"Your location is more than {MAX_GPS_AGE_SECONDS} seconds old. Keep this page open for a fresh reading; if it does not update, turn Location off and on in Profile.",
    "unavailable": "Your phone cannot find its position. Turn on location services, move outside or closer to a window, and try again.",
    "timeout": "Finding your location took too long. Move outside or closer to a window, then turn Location off and on in Profile to retry.",
    "unsupported": "This browser cannot share your location. Open the app's HTTPS address in a browser with location support, such as Safari or Chrome, and allow location access.",
    "invalid": "Your location reading could not be used. Reload the page and turn Location on in Profile to request a fresh reading.",
}


def location_problem(problem, accuracy=None):
    if problem:
        return LOCATION_MESSAGES.get(problem, LOCATION_MESSAGES["invalid"])
    if accuracy is not None and accuracy > MAX_GPS_ACCURACY_M:
        return (f"Your location is accurate to about {accuracy:.0f} m; this action needs "
                f"{MAX_GPS_ACCURACY_M:.0f} m or better. Move outside or closer to a window and wait for a more accurate reading.")
    return None


def stake_problems(opponent, stake, available_points):
    return [
        "No opponent selected. Choose a player under Who, then try again." if opponent is None else None,
        (f"This stake needs {stake} available points; you have {format_points(available_points)}. "
         "Choose a lower stake or earn more points with an accepted check-in. Points reserved for another duel cannot be reused.")
        if available_points < stake else None,
    ]


def duel_closed_message(season):
    now = current_time()
    if utc(now) >= utc(season.ends_at):
        return "This season has ended. Create or join a new lobby to play another duel."
    opening = next_opening(now, season)
    if opening:
        local = opening.astimezone(ZoneInfo(season.timezone_name))
        return f"Duels are closed right now. Return {local:%a %d %b at %H:%M} ({season.timezone_name}) when scoring opens."
    return "Duels are closed right now. Open Check in to see the scoring schedule or choose another active lobby."


def opponent_message(own, lobby):
    if lobby.game_mode == "team":
        if not own.team_id:
            return "You need a team first. Open your lobby on the Lobby page and join a team, then return to Minigames."
        return "This game needs a rival team. Share the lobby invite code and ask another player to join a different team."
    return "This game needs another player. Share the lobby invite code and ask another player to join this lobby."


CHECKIN_MESSAGES = {
    "team_required": "You need a team to check in. Open your lobby on the Lobby page and join a team.",
    "scoring_closed": "Scoring is closed. Refresh Check in to see the next opening in your lobby's timezone; if the season ended, choose a new lobby.",
    "cooldown": "A recent check-in is still within the two-minute cooldown. Keep your photo and selections, wait until the countdown ends, then try again.",
    "invalid_selection": "This drink or size is not supported. Choose a drink and one of its listed sizes, then try again.",
    "invalid_photo": "The photo could not be accepted. Choose Retake photo and take a fresh camera photo, then submit again.",
    "missing_photo": "A camera photo is required. Take a photo of your drink before submitting.",
    "unknown_drink_type": "This drink type is not supported. Choose a drink from the listed options.",
    "missing_amount": "This drink needs an amount greater than zero. Enter its amount and try again.",
    "duplicate_check_in": "This drink was already logged recently. Check Photos for the saved entry before recording another drink.",
    "location_unavailable": "A current phone location is required. Open Profile → Location, allow access and turn tracking on, then retry.",
    "location_uncertain": f"Your location could not be verified accurately enough (maximum {MAX_GPS_ACCURACY_M:.0f} m). Move outside and wait for a fresh reading before retrying.",
    "invalid_territory": "The territory could not be verified. Refresh the page for a fresh location and retry; if this continues, contact the app organizer.",
    "correction_closed": "The correction window has closed. Drinks can only be corrected within two minutes of submission and before the season ends. Refresh to view the saved entry.",
    "correction_conflict": "This entry changed in another session. Refresh and review the saved drink before trying another correction.",
    "duel_entry_locked": "This drink belongs to a shared duel and cannot be corrected separately. Open Minigames to review the agreed drink.",
    "season_still_active": "This season is still running. Open the existing lobby to continue playing.",
    "lobby_already_started": "This lobby already has its competition. Open the existing lobby; create a new lobby for a new competition.",
    "invalid_timezone": "The lobby timezone is not supported. Enter or select a timezone such as Europe/Lisbon, then retry lobby setup.",
    "invalid_rules": "The season rules could not be accepted. Ask the app organizer to check the lobby setup, then refresh.",
    "scoring_version_mismatch": "This action does not match the season's scoring rules. Reopen the lobby and select its current competition before trying again.",
    "season_has_legacy_entries": "This season already has historical drinks and cannot be upgraded. Create a new lobby for the current rules; the old history is kept.",
    "season_rules_frozen": "The rules of an existing season cannot be changed. Create a new lobby to use different rules or a different timezone.",
    "entry_identity_frozen": "The original player, season, photo and location of a drink cannot be changed. Use Correct drink or size for an eligible correction within two minutes of submission.",
}


def checkin_message(reason):
    return CHECKIN_MESSAGES.get(reason, "This action could not be accepted. Refresh and check the saved entry before retrying; if it continues, contact the app organizer.")
