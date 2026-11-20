"""Send personal lobby invitations and review them as the signed-in recipient."""
from uuid import UUID

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError

import data.db as db
from password_email import send_lobby_invite_email

LOAD_ERRORS = (APIError, RequestError, RuntimeError, OSError)
SEND_ERRORS = {
    "invite_creator_only": "Only the active lobby creator can send invitations.",
    "invite_lobby_closed": "Invitations are available once lobby setup is complete and until the lobby ends.",
    "invite_friends_only": "You can only invite accepted friends.",
    "invite_already_member": "This friend is already in the lobby.",
    "invite_email_unavailable": "This friend cannot receive invitations yet.",
    "invite_pending": "This friend already has a pending invitation.",
    "invite_rate_limited": "The invitation limit was reached. Try again later.",
}
RESPONSE_ERRORS = {
    "invite_unavailable": "This invitation is no longer available for your account.",
    "lobby_full": "This lobby is full. You can still decline the invitation.",
    "lobby_finished": "This lobby has finished.",
}


def _session_is_current(player_id):
    # Dialog and timed-fragment interactions can bypass the page's login bootstrap.
    if st.session_state.get("player_id") != player_id:
        return False
    player = db.get_player(player_id)
    return bool(player and player.email and player.pin_hash == st.session_state.get("credential_version"))


def show_invite_player(player_id, lobby_id, memberships):
    key = f"_invite_picker_{lobby_id}"
    if st.button("Invite player", key=f"invite_player_{lobby_id}"):
        st.session_state[key] = not st.session_state.get(key, False)
    if not st.session_state.get(key):
        return
    try:
        relationships = db.list_friendships(player_id)
        members = {member.player_id for member in memberships if member.left_at is None}
        friend_ids = {
            row["recipient_id"] if row["sender_id"] == player_id else row["sender_id"]
            for row in relationships if row["status"] == "accepted"
        } - members
        names = {p["id"]: p["display_name"] for p in db.list_public_usernames()
                 if p["id"] in friend_ids} if friend_ids else {}
    except LOAD_ERRORS:
        st.error("Your friends could not be loaded. Try again.")
        return
    if not names:
        st.caption("You have no accepted friends outside this lobby.")
        return
    for friend_id, name in sorted(names.items(), key=lambda item: (item[1].casefold(), item[0])):
        if st.button(f"Invite {name}", key=f"invite_{lobby_id}_{friend_id}"):
            _send_invite(player_id, lobby_id, friend_id)


def _send_invite(player_id, lobby_id, friend_id):
    try:
        if not _session_is_current(player_id):
            st.error("Sign in again to send invitations.")
            return
        invite = db.issue_lobby_invitation(player_id, lobby_id, friend_id)
    except APIError as error:
        st.error(SEND_ERRORS.get(error.message, "Could not save the invitation. Try again."))
        return
    except LOAD_ERRORS:
        st.error("Could not save the invitation. Try again.")
        return
    try:
        send_lobby_invite_email(
            invite["recipient_email"], invite["invite_id"], invite["inviter_name"], invite["lobby_name"]
        )
    except RuntimeError:
        st.warning("Email delivery could not be confirmed. Your friend can open the invitation under Pending invites.")
    else:
        st.success("Invitation saved and submitted for email delivery.")


def show_pending_lobby_invites(player_id):
    linked_invite = st.query_params.get("lobby_invite")
    if linked_invite is not None:
        try:
            linked_invite = str(UUID(linked_invite))
        except ValueError:
            linked_invite = ""

    notice = st.session_state.pop("_lobby_invite_notice", None)
    if notice:
        st.success(notice)
    try:
        invitations = db.pending_lobby_invitations(player_id)
    except LOAD_ERRORS:
        st.warning("Pending invites could not be loaded. Use Refresh lobbies to try again.")
        return
    if linked_invite is not None and not any(row["invite_id"] == linked_invite for row in invitations):
        st.info("This invitation is no longer available for your account.")
    if not invitations:
        return

    st.subheader("Pending invites")
    for invite in sorted(invitations, key=lambda row: row["invite_id"] != linked_invite):
        invite_id = invite["invite_id"]
        with st.container(border=True):
            st.text(invite["lobby_name"])
            st.text(f"Invited by {invite['inviter_name']}")
            accept, decline = st.columns(2)
            if accept.button("Accept", key=f"accept_lobby_invite_{invite_id}", type="primary"):
                _respond(player_id, invite_id, "accept")
            if decline.button("Decline", key=f"decline_lobby_invite_{invite_id}"):
                _respond(player_id, invite_id, "decline")


def _respond(player_id, invite_id, response):
    try:
        if not _session_is_current(player_id):
            st.error("Sign in again to respond to invitations.")
            return
        lobby_name = db.respond_to_lobby_invitation(player_id, invite_id, response)
    except APIError as error:
        st.error(RESPONSE_ERRORS.get(error.message, "Could not respond to the invitation. Try again."))
    except LOAD_ERRORS:
        st.error("Could not respond to the invitation. Try again.")
    else:
        st.session_state["_lobby_invite_notice"] = (
            f"You joined {lobby_name}." if response == "accept" else f"You declined the invitation to {lobby_name}."
        )
        if st.query_params.get("lobby_invite") == invite_id:
            del st.query_params["lobby_invite"]
        st.rerun()
