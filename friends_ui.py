"""Private friend controls for the authenticated Profile page."""
import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError

import data.db as db
from core.friends import search_usernames
from profile_picture_ui import picture_identity, show_picture_identity


def friendship_action(player_id, label, other, operation, *, key_prefix="friend", refresh_label="Refresh friends"):
    if st.button(label, key=f"{key_prefix}_{operation}_{other}"):
        try:
            db.change_friendship(player_id, other, operation)
        except ValueError as exc:
            st.error(str(exc))
        except APIError as exc:
            if exc.code == "40001":
                st.error(f"This request changed. {refresh_label} and try again.")
            else:
                st.error("Could not update friends. Please try again later.")
        except (RuntimeError, OSError, RequestError):
            st.error("Could not update friends. Please try again later.")
        else:
            st.rerun()


def show_friends(player_id: str):
    st.header("Friends")
    st.caption("Your friends list is private. Search finds usernames across the app.")
    if st.button("Refresh friends"):
        st.rerun()
    try:
        users = db.list_public_usernames()
        relationships = db.list_friendships(player_id)
    except (APIError, RuntimeError, OSError, RequestError):
        st.error("Friends are unavailable. Please try again later.")
        return
    names = {p["id"]: p["display_name"] for p in users}
    by_other = {r["recipient_id"] if r["sender_id"] == player_id else r["sender_id"]: r for r in relationships}

    def identity(other):
        if by_other.get(other, {}).get("status") in ("accepted", "pending"):
            show_picture_identity(player_id, other, names.get(other, "Unknown player"), size=40)
        else:
            picture_identity(names.get(other, "Unknown player"), size=40)

    def action(label, other, operation):
        friendship_action(player_id, label, other, operation)

    st.subheader("Incoming requests")
    incoming = [(other, r) for other, r in by_other.items() if r["status"] == "pending" and r["recipient_id"] == player_id]
    if not incoming:
        st.caption("No incoming requests.")
    for other, _ in incoming:
        identity(other)
        action("Accept", other, "accept")
        action("Decline", other, "decline")

    st.subheader("Your friends")
    accepted = sorted((other for other, r in by_other.items() if r["status"] == "accepted"), key=lambda other: names.get(other, "").casefold())
    if not accepted:
        st.caption("No friends yet. Search for a username below.")
    for other in accepted:
        identity(other)
        action("Remove friend", other, "remove")

    st.subheader("Outgoing requests")
    outgoing = [other for other, r in by_other.items() if r["status"] == "pending" and r["sender_id"] == player_id]
    if not outgoing:
        st.caption("No outgoing requests.")
    for other in outgoing:
        identity(other)
        action("Cancel request", other, "cancel")

    st.subheader("Find players")
    query = st.text_input("Search usernames", max_chars=80)
    results = search_usernames(query, users, player_id)
    if query.strip() and not results:
        st.info("No matching usernames found.")
    for user in results:
        other = user["id"]
        identity(other)
        status = by_other.get(other, {}).get("status")
        if status == "accepted":
            st.caption("Already friends")
        elif status == "pending":
            st.caption("Request pending — see requests above.")
        else:
            if status == "declined":
                st.caption("After a decline, wait 10 minutes before sending another request.")
            action("Send friend request", other, "request")
